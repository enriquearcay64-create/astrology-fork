"""Stateless, tool-free Gemini transport and append-only execution receipts.

Local orchestrator/storage are trusted. Hashes detect changes against preserved
receipts; they are not independent attestation against an owner rewriting all files.
"""
from __future__ import annotations
import contextlib
import fcntl
import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from .benchmark_integrity import canonical_bytes, sha256, load_json, require_equal, git_commit
from .exceptions import BenchmarkIntegrityError


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BenchmarkIntegrityError('Duplicate response JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise BenchmarkIntegrityError('Non-finite JSON value: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def code_context(repository):
    repository = Path(repository)
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=repository).decode().split('\0')
    relevant = sorted({n for n in names if n and (n.startswith(('astrology/', 'scripts/', 'assets/')) or n in ('SKILL.md', 'pyproject.toml', 'requirements.txt', 'requirements-dev.txt'))})
    digest = sha256(canonical_bytes({name: sha256((repository/name).read_bytes()) if (repository/name).is_file() else None for name in relevant}))
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository).strip())
    return {'artifact_generation_commit_sha': git_commit(repository), 'source_sha256': digest, 'working_tree_dirty': dirty}


class GeminiTransport:
    """Single contents item; no history, caches, tools, files or repository access.

    API reference: https://ai.google.dev/api/generate-content
    No default model: the operator must supply the actual configured identifier.
    """
    provider = 'google-gemini-api'
    fixture = False

    def __init__(self, model, *, temperature=0.7, max_output_tokens=32768, timeout=180, thinking_level=None):
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise ValueError('An explicit Gemini model identifier is required')
        if not 0 <= temperature <= 2 or type(max_output_tokens) is not int or max_output_tokens <= 0:
            raise ValueError('Invalid generation settings')
        self.model = model
        self.settings = {'temperature': temperature, 'maxOutputTokens': max_output_tokens, 'responseMimeType': 'application/json'}
        if thinking_level is not None:
            tl = str(thinking_level).lower()
            if tl not in {'low', 'medium', 'high'}:
                raise ValueError(f'Invalid thinking level: {thinking_level}. Expected low, medium, or high.')
            self.thinking_level = tl
            self.settings['thinkingConfig'] = {'thinkingLevel': tl.upper()}
        else:
            self.thinking_level = None
        self.timeout = timeout

    def request(self, prompt):
        return {'systemInstruction': {'parts': [{'text': 'Use only the supplied input. Return the requested JSON. You have no tools or external context.'}]},
                'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'tools': [], 'generationConfig': self.settings}

    def send(self, request):
        key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not key:
            raise BenchmarkIntegrityError('Configure GEMINI_API_KEY locally; no model request was sent')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
        req = urllib.request.Request(url, data=canonical_bytes(request), headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read()

    @staticmethod
    def extract(raw):
        response = strict_json(raw)
        candidates = response.get('candidates', [])
        if len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP':
            raise BenchmarkIntegrityError('Model response blocked, missing or incomplete; raw response retained')
        parts = candidates[0].get('content', {}).get('parts', [])
        if any(set(p) - {'text', 'thought', 'thoughtSignature'} for p in parts):
            raise BenchmarkIntegrityError('Tool/non-text response is forbidden')
        text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
        payload = strict_json(text)
        metadata = {name: response.get(name) for name in ('modelVersion', 'responseId', 'usageMetadata')}
        return payload, metadata


class RunStore:
    """Fixed artifacts, linked event hashes, exclusive writes, and single-writer stages."""
    def __init__(self, root):
        self.root = Path(root).resolve()

    @classmethod
    def create(cls, root, repository, configuration, *, fixture=False, audit_record=None):
        root = Path(root)
        context = code_context(repository)
        if not fixture:
            if context['working_tree_dirty']:
                raise BenchmarkIntegrityError('Live generation requires reviewed, committed code')
            if not isinstance(audit_record, dict) or audit_record.get('verdict') != 'benchmark-ready' or audit_record.get('source_sha256') != context['source_sha256'] or audit_record.get('commit_sha') != context['artifact_generation_commit_sha']:
                raise BenchmarkIntegrityError('Independent benchmark-ready audit for this code is required')
        root.mkdir(parents=True, exist_ok=False)
        store = cls(root)
        store.put_json('run.json', {'run_id': root.name, 'repository': str(Path(repository).resolve()), 'code_context': context,
                                   'configuration': configuration, 'fixture': fixture, 'audit_record': audit_record})
        store.event('created', ['run.json'])
        return store

    def path(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9._/-]+', name) or '..' in name.split('/'):
            raise BenchmarkIntegrityError('Invalid artifact name')
        path = self.root/name
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise BenchmarkIntegrityError('Artifact path escapes run')
        return path

    def put(self, name, data):
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return sha256(data)

    def put_json(self, name, value):
        return self.put(name, canonical_bytes(value))

    @contextlib.contextmanager
    def lock(self):
        with self.path('.writer.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise BenchmarkIntegrityError('Another writer owns this run') from error
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def verify(self):
        previous = None
        events = []
        for index, path in enumerate(sorted(self.root.glob('events/*.json'))):
            if path.name != f'{index:06d}.json':
                raise BenchmarkIntegrityError('Missing/reordered execution event')
            record = load_json(path)
            if record['previous_sha256'] != previous:
                raise BenchmarkIntegrityError('Broken execution event chain')
            for name, digest in record['artifacts'].items():
                if not self.path(name).is_file() or sha256(self.path(name).read_bytes()) != digest:
                    raise BenchmarkIntegrityError('Changed/missing execution artifact: ' + name)
            previous = sha256(path.read_bytes())
            events.append(record)
        return events

    def event(self, action, artifacts):
        events = self.verify()
        previous = sha256(self.path(f'events/{len(events)-1:06d}.json').read_bytes()) if events else None
        record = {'action': action, 'at': datetime.now(timezone.utc).isoformat(), 'previous_sha256': previous,
                  'artifacts': {name: sha256(self.path(name).read_bytes()) for name in artifacts}}
        self.put_json(f'events/{len(events):06d}.json', record)
        return record

    def assert_code(self):
        origin = load_json(self.path('run.json'))
        recorded = origin['code_context']
        current = code_context(origin['repository'])
        for field in ('artifact_generation_commit_sha', 'source_sha256'):
            require_equal(current[field], recorded[field], 'generation code ' + field)
        if not origin.get('fixture') and current.get('working_tree_dirty'):
            raise BenchmarkIntegrityError('Working tree cannot be dirty during live benchmark execution')

    def invoke(self, stage, prompt, transport):
        if stage not in {'selection', 'author', 'reviewer', 'evaluator'}:
            raise BenchmarkIntegrityError('Unknown execution role')
        with self.lock():
            self.assert_code()
            events = self.verify()
            prerequisite = {'selection': 'prepared', 'author': 'selection:validated', 'reviewer': 'author:validated', 'evaluator': 'blind:committed'}[stage]
            if prerequisite not in [event['action'] for event in events]:
                raise BenchmarkIntegrityError('Missing stage prerequisite: ' + prerequisite)
            prompt_name = {'selection': 'author_selection_prompt.txt', 'author': 'author_prompt.txt', 'reviewer': 'reviewer_prompt.txt', 'evaluator': 'evaluator_prompt.txt'}[stage]
            if not self.path(prompt_name).is_file() or self.path(prompt_name).read_text() != prompt:
                raise BenchmarkIntegrityError('Request differs from the prepared stage prompt')
            fixture = load_json(self.path('run.json'))['fixture']
            if not fixture and type(transport) is not GeminiTransport:
                raise BenchmarkIntegrityError('Live runs require the isolated API transport')
            request = transport.request(prompt)
            expected = {'model': transport.model, 'provider': transport.provider, 'request': request, 'fixture_transport': bool(transport.fixture), 'thinking_level': getattr(transport, 'thinking_level', None)}
            prefix = f'stages/{stage}'
            if self.path(prefix + '/receipt.json').exists():
                require_equal(load_json(self.path(prefix + '/request.json')), expected, 'resumed request')
                self.verify_response(stage)
                return load_json(self.path(prefix + '/parsed.json'))
            # A pending/crashed request is not silently retried or overwritten.
            self.put_json(prefix + '/request.json', expected)
            self.put(prefix + '/prompt.txt', prompt.encode())
            self.event(stage + ':request', [prefix + '/request.json', prefix + '/prompt.txt'])
            try:
                raw = transport.send(request)
            except Exception as error:
                self.put_json(prefix + '/failure.json', {'type': type(error).__name__, 'message': 'Transport failed; inspect configuration/network. No automatic retry.'})
                self.event(stage + ':failed', [prefix + '/failure.json'])
                raise
            self.put(prefix + '/response.raw.json', raw)
            self.event(stage + ':response', [prefix + '/response.raw.json'])
            parsed, metadata = GeminiTransport.extract(raw)
            self.put_json(prefix + '/parsed.json', parsed)
            self.put_json(prefix + '/receipt.json', {'request_sha256': sha256(canonical_bytes(expected)),
                'raw_sha256': sha256(raw), 'parsed_sha256': sha256(canonical_bytes(parsed)), 'runtime': metadata})
            self.event(stage + ':parsed', [prefix + '/parsed.json', prefix + '/receipt.json'])
            return parsed

    def verify_response(self, stage):
        self.verify()
        prefix = f'stages/{stage}'
        request_record = load_json(self.path(prefix + '/request.json'))
        request = request_record['request']
        if set(request) != {'systemInstruction', 'contents', 'tools', 'generationConfig'} or request['tools'] != []:
            raise BenchmarkIntegrityError('Captured request enabled external tools/context')
        require_equal(request['contents'], [{'role': 'user', 'parts': [{'text': self.path(prefix + '/prompt.txt').read_text()}]}], 'stateless request contents')
        raw = self.path(prefix + '/response.raw.json').read_bytes()
        parsed, metadata = GeminiTransport.extract(raw)
        require_equal(parsed, load_json(self.path(prefix + '/parsed.json')), 'raw response derivation')
        expected = {'request_sha256': sha256(self.path(prefix + '/request.json').read_bytes()), 'raw_sha256': sha256(raw),
                    'parsed_sha256': sha256(canonical_bytes(parsed)), 'runtime': metadata}
        require_equal(expected, load_json(self.path(prefix + '/receipt.json')), 'execution receipt')
        return parsed
