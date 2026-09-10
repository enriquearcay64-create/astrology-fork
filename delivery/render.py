"""Subject-neutral PDF presentation. Does not calculate or approve astrology."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                               Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

_RUNTIME_VALUE = os.environ.get('CODEX_WORKSPACE_DEPENDENCIES')
RUNTIME = Path(_RUNTIME_VALUE).expanduser() if _RUNTIME_VALUE else None
INK, MUTED, GOLD, SAGE, SAND, PAPER = [colors.HexColor(c) for c in
    ('#213E40', '#576C6A', '#966C3E', '#EDF3EF', '#F6F0E6', '#FBF8F3')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def styles():
    bundled = (RUNTIME / 'native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype'
               if RUNTIME else Path('__no_bundled_runtime__'))
    font_candidates = [Path(os.environ['ASTROLOGY_DELIVERY_FONT_DIR'])] if os.environ.get('ASTROLOGY_DELIVERY_FONT_DIR') else []
    font_candidates += [bundled, Path('/usr/share/fonts/truetype/crosextra')]
    fonts = next((path for path in font_candidates if all((path / name).exists() for name in
        ('Caladea-Regular.ttf','Caladea-Bold.ttf','Carlito-Regular.ttf','Carlito-Bold.ttf'))), None)
    if fonts:
        for name, file in [('Body', 'Caladea-Regular.ttf'), ('BodyBold', 'Caladea-Bold.ttf'),
                           ('Sans', 'Carlito-Regular.ttf'), ('SansBold', 'Carlito-Bold.ttf')]:
            pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    else:
        for alias, built_in in [('Body','Times-Roman'),('BodyBold','Times-Bold'),
                                ('Sans','Helvetica'),('SansBold','Helvetica-Bold')]:
            pdfmetrics.registerFont(pdfmetrics.Font(alias, built_in, 'WinAnsiEncoding'))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='Body', boldItalic='BodyBold')
    pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansBold', italic='Sans', boldItalic='SansBold')
    base = ParagraphStyle('body', fontName='Sans', fontSize=11.2, leading=16.1,
                          textColor=INK, spaceAfter=11, allowWidows=0, allowOrphans=0)
    return {'body': base,
            'title': ParagraphStyle('title', parent=base, fontName='Body', fontSize=46, leading=52),
            'h2': ParagraphStyle('h2', parent=base, fontName='BodyBold', fontSize=25, leading=29, spaceBefore=18, spaceAfter=18, keepWithNext=True),
            'h3': ParagraphStyle('h3', parent=base, fontName='SansBold', fontSize=12, leading=16, textColor=GOLD, spaceBefore=14, keepWithNext=True),
            'small': ParagraphStyle('small', parent=base, fontSize=9.4, leading=13, textColor=MUTED),
            'quote': ParagraphStyle('quote', parent=base, fontName='Body', fontSize=18, leading=23)}


def inline(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)


def parse(text):
    """Presentation blocks only; the production parser remains authoritative."""
    blocks, pending = [], []
    def flush():
        if pending:
            blocks.append(('body', ' '.join(pending)))
            pending.clear()
    for line in text.splitlines():
        if not line.strip():
            flush()
        elif line.startswith('#'):
            flush()
            match = re.fullmatch(r'(#{1,3}) (.+)', line)
            if not match:
                raise ValueError('Unsupported heading; preserve the approved source.')
            blocks.append(('h' + str(len(match[1])), match[2]))
        elif re.match(r'^(?:[-*+] |\d+[.)] )', line):
            flush()
            blocks.append(('body', line))
        else:
            pending.append(line.strip())
    flush()
    return blocks


def render(config_path):
    cfg = json.loads(config_path.read_text())
    root = config_path.parent
    source = (root / cfg['reading']).resolve()
    appendix = (root / cfg['appendix']).resolve()
    hashes = {str(p): digest(p) for p in (source, appendix)}
    if cfg['source_sha256'] != hashes[str(source)]:
        raise ValueError('Reading changed: inspect source before updating presentation.')
    if cfg['appendix_sha256'] != hashes[str(appendix)]:
        raise ValueError('Appendix changed: inspect source before updating presentation.')
    raw = source.read_text()
    blocks = parse(raw)
    highlights = cfg.get('highlights', {})
    quotes = cfg.get('pull_quotes', {})
    examples = cfg.get('example_excerpts', {})
    valid = {hashlib.sha256(t.encode()).hexdigest() for k, t in blocks if k == 'body'}
    if set(highlights) - valid or any(v not in ('example', 'quote') for v in highlights.values()):
        raise ValueError('Highlight must identify an existing complete paragraph and a supported style.')
    by_hash = {hashlib.sha256(t.encode()).hexdigest():t for k,t in blocks if k == 'body'}
    if set(quotes)-valid or set(quotes)&set(highlights) or any(not q or by_hash[h].count(q)!=1 for h,q in quotes.items()):
        raise ValueError('Pull quote must be one exact, unique excerpt of its source paragraph.')
    if set(examples)-valid or set(examples)&(set(highlights)|set(quotes)) or any(not q or by_hash[h].count(q)!=1 for h,q in examples.items()):
        raise ValueError('Example excerpt must be one exact, unique excerpt, with no conflicting style.')
    output = (root / cfg.get('output_dir', 'output/pdf')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / cfg['report_filename'], output / cfg['appendix_filename']]
    if len(set(paths)) != 2 or any(p.parent != output or p.suffix != '.pdf' for p in paths):
        raise ValueError('Provide two distinct PDF basenames.')
    if any(p in (source, appendix) for p in paths):
        raise ValueError('Output cannot overwrite a source.')
    s = styles()
    s['technical_h2'] = ParagraphStyle('technical_h2', parent=s['h2'], fontSize=19,
                                      leading=23, spaceBefore=12, spaceAfter=10)
    intro_style = cfg.get('introduction_style', 'body')
    if intro_style not in ('body', 'small'):
        raise ValueError('Introduction style must be body or small; its wording is immutable.')
    def para(t, style='body'):
        return Paragraph(inline(t), s[style])
    def consultation_panel():
        panel = cfg['period_overview']
        rows = panel['rows']
        if not rows or any(len(row) != 3 for row in rows):
            raise ValueError('Period overview requires three columns per row.')
        heading = para('O período em uma página', 'h2')
        heading.anchor = 'period-overview'
        table = Table([[para(cell,'small') for cell in row] for row in rows],
                      colWidths=[105,135,223], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),SAGE),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[PAPER,SAND]),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
        return [PageBreak(),heading,para(panel['note'],'small'),Spacer(1,12),table,PageBreak()]
    panel = cfg.get('period_overview')
    if panel and sum(kind == 'h2' and text == panel['before_heading'] for kind,text in blocks) != 1:
        raise ValueError('Period overview must precede one existing section.')
    anchors = iter(range(100000))
    def flow(items, technical=False):
        result = []
        in_introduction = not technical
        for index, (kind, text) in enumerate(items):
            if kind == 'h1':
                heading = para(text, 'h2')
                heading.page_label = text
                result.append(heading)
                continue
            if kind in ('h2', 'h3'):
                if kind == 'h2':
                    in_introduction = False
                if not technical and index == 0 and kind == 'h3':
                    intro = para(text,'h3')
                    intro.page_label = text
                    result.append(intro)
                    continue
                if kind == 'h2' and not technical and panel and text == panel['before_heading']:
                    result.extend(consultation_panel())
                elif kind == 'h2' and text in cfg.get('page_break_before',[]):
                    result.append(PageBreak())
                heading = para(text, 'technical_h2' if technical and kind == 'h2' else kind)
                if kind == 'h2':
                    heading.anchor = f'section-{next(anchors)}'
                result.append(heading)
                continue
            if technical and '|' in text:
                # Technical tables are read line-by-line separately below.
                result.append(para(text, 'small'))
                continue
            mode = highlights.get(hashlib.sha256(text.encode()).hexdigest()) if not technical else None
            quote = quotes.get(hashlib.sha256(text.encode()).hexdigest()) if not technical else None
            example = examples.get(hashlib.sha256(text.encode()).hexdigest()) if not technical else None
            quote = example or quote
            if quote:
                before, after = text.split(quote,1)
                if before.strip():
                    result.append(para(before.strip()))
                card = Table([[[para('NA PRÁTICA' if example else 'UMA DISTINÇÃO PARA GUARDAR','small'),para(quote,'body' if example else 'quote')]]],colWidths=[463])
                card.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SAGE if example else SAND),('LINEBEFORE',(0,0),(0,-1),2,GOLD),
                    ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),
                    ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
                result.extend([card,Spacer(1,15)])
                if after.strip():
                    result.append(para(after.strip()))
                continue
            if mode:
                cell = [para('NA PRÁTICA' if mode == 'example' else 'UMA DISTINÇÃO PARA GUARDAR', 'small'),
                        para(text, 'quote' if mode == 'quote' else 'body')]
                card = Table([[cell]], colWidths=[463])
                card.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SAND if mode == 'quote' else SAGE),
                    ('LINEBEFORE',(0,0),(0,-1),2,GOLD),('LEFTPADDING',(0,0),(-1,-1),16),
                    ('RIGHTPADDING',(0,0),(-1,-1),16),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
                result.extend([card, Spacer(1,15)])
            else:
                result.append(para(text, 'small' if technical else intro_style if in_introduction else 'body'))
        return result
    def technical_flow():
        result = []
        for chunk in re.split(r'\n\s*\n', appendix.read_text()):
            lines = chunk.strip().splitlines()
            if lines and all(line.lstrip().startswith('- ') for line in lines):
                records = [re.sub(r'\*\*(.*?)\*\*',r'\1',line.lstrip()[2:]) for line in lines]
                separator = ':' if all(':' in line and (';' not in line or line.index(':') < line.index(';')) for line in records) else ';'
                rows = []
                for line in records:
                    left, mark, right = line.partition(separator)
                    rows.append([left + mark, right.strip()] if mark else [line,''])
                widths = [110,353] if separator == ':' and max(len(row[0]) for row in rows) < 24 else [220,243]
                table = Table([[para(c,'small') for c in row] for row in rows],colWidths=widths)
                table.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[SAGE,PAPER]),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
                    ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
                result.extend([table,Spacer(1,15)])
                continue
            if len(lines) > 1 and '|' in lines[0] and re.fullmatch(r'[ |:\-]+', lines[1]):
                rows = [[c.strip() for c in line.strip().strip('|').split('|')] for i,line in enumerate(lines) if i != 1]
                n = len(rows[0])
                if any(len(r) != n for r in rows):
                    raise ValueError('Irregular appendix table.')
                widths = cfg.get('technical_table_widths', {}).get('|'.join(rows[0]), [463/n]*n)
                if len(widths) != n or any(not isinstance(w, (int, float)) or w <= 0 for w in widths) or abs(sum(widths)-463) > .01:
                    raise ValueError('Technical table widths must match columns and total 463 points.')
                table = Table([[para(c,'small') for c in row] for row in rows], colWidths=widths, repeatRows=1)
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),SAGE),('ROWBACKGROUNDS',(0,1),(-1,-1),[PAPER,SAND]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
                result.extend([table, Spacer(1,15)])
            else:
                technical_text = '\n'.join(line.lstrip().removeprefix('> ') for line in chunk.splitlines())
                result.extend(flow(parse(technical_text), True))
        return result
    class Doc(SimpleDocTemplate):
        def beforeDocument(self):
            self.running = 'SEU PERCURSO DE LEITURA'
        def beforePage(self):
            self.page_heading = self.running
            self.page_seen = False
        def afterFlowable(self, f):
            if hasattr(f, 'anchor') or hasattr(f, 'page_label'):
                if not self.page_seen:
                    self.page_heading = f.getPlainText()
                self.running = f.getPlainText()
            if hasattr(f, 'anchor'):
                self.canv.bookmarkPage(f.anchor)
                self.notify('TOCEntry',(0,f.getPlainText(),self.page,f.anchor))
            if isinstance(f,(Paragraph,Table)):
                self.page_seen = True
        def afterPage(self):
            if self.page > 1:
                self.canv.setFont('Sans',8)
                self.canv.setFillColor(MUTED)
                self.canv.drawString(66,811,self.page_heading.upper()[:75])
    def page(c,d):
        c.setFillColor(SAND if d.page == 1 else PAPER)
        c.rect(0,0,595,842,fill=1,stroke=0)
        if d.page > 1:
            c.setStrokeColor(GOLD); c.line(66,47,529,47)
            c.setFont('Sans',8); c.setFillColor(MUTED)
            c.drawString(66,32,cfg['display_name'] + ' / LEITURA NATAL')
            c.drawRightString(529,32,str(d.page))
    for path, standalone in zip(paths, (False,True)):
        title = 'Apêndice de consulta' if standalone else 'Leitura natal'
        story = [Spacer(1,91),para('CADERNO PESSOAL / ASTROLOGIA','small'),para(cfg['display_name'],'title'),para(title,'h2'),Spacer(1,30)]
        story.extend(para(t,'small') for t in cfg.get('metadata',[]))
        story.extend([PageBreak(),para('Seu percurso de leitura','h2')])
        toc = TableOfContents(); toc.levelStyles=[s['small']]
        story.extend([toc,PageBreak()])
        if not standalone:
            story.extend(flow(blocks)); story.append(PageBreak())
        story.extend(technical_flow())
        Doc(str(path),pagesize=(595,842),leftMargin=66,rightMargin=66,topMargin=66,bottomMargin=66,
            title=cfg['display_name']+' / '+title,author='').multiBuild(story,onFirstPage=page,onLaterPages=page)
    qa = {'source_sha256':hashes,'presentation_config_sha256':digest(config_path),
          'production_validation':'not performed by renderer','period_overview':bool(panel),'pdfs':[]}
    render_dir = Path(tempfile.mkdtemp(prefix='render-',dir=output))
    for index,path in enumerate(paths):
        with pdfplumber.open(path) as pdf:
            bad = [(i+1,w['text']) for i,p in enumerate(pdf.pages) for w in p.extract_words()
                   if w['x0'] < 59 or w['x1'] > 536 or w['top'] < 22 or w['bottom'] > 815]
            missing = []
            if index == 0:
                extracted = re.sub(r'\s+', '', ''.join(p.crop((59,60,536,795)).extract_text() or '' for p in pdf.pages[2:])).replace('UMADISTINÇÃOPARAGUARDAR','').replace('NAPRÁTICA','')
                cursor = 0
                for kind, text in blocks:
                    expected = re.sub(r'\s+', '', para(text).getPlainText())
                    found = extracted.find(expected, cursor)
                    if found < 0:
                        missing.append(hashlib.sha256(text.encode()).hexdigest())
                    else:
                        cursor = found + len(expected)
            qa['pdfs'].append({'path':str(path),'sha256':digest(path),'pages':len(pdf.pages),'out_of_bounds':bad,'missing_or_reordered_reading_blocks':missing})
        configured = os.environ.get('ASTROLOGY_PDFTOPPM')
        bundled_pdftoppm = RUNTIME/'bin/override/pdftoppm' if RUNTIME else None
        pdftoppm = configured or shutil.which('pdftoppm') or (str(bundled_pdftoppm) if bundled_pdftoppm and bundled_pdftoppm.exists() else None)
        if not pdftoppm:
            raise RuntimeError('pdftoppm is required for visual QA; install Poppler or set ASTROLOGY_PDFTOPPM.')
        subprocess.run([pdftoppm,'-scale-to','1100','-png',str(path),str(render_dir/f'pdf-{index}')],check=True,capture_output=True)
    if any(digest(Path(p)) != h for p,h in hashes.items()):
        raise ValueError('Source changed during rendering.')
    qa['renders'] = str(render_dir)
    qa['visual_review'] = 'pending operator inspection'
    (output/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
    if any(p['out_of_bounds'] or p['missing_or_reordered_reading_blocks'] for p in qa['pdfs']):
        raise ValueError('Inspect layout or text preservation findings in qa.json.')
    print(json.dumps(qa,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config',type=Path)
    render(parser.parse_args().config.resolve())
