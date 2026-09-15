"""Regression fixtures exercise false-success risks without loading any model."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave
from fish_s2_evidence import audit


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'clip.wav'
        with wave.open(str(self.path),'wb') as w:
            w.setparams((1,2,44100,0,'NONE','not compressed'))
            w.writeframes(b'\x00\x10\x00\xf0'*2205)
        self.a = [{'case_id':'one','ok':True,'exit_code':0}]
        self.g = [{'case_id':'one','exit_status':'ok','hit_token_limit':False,'generation_seconds':.2,'audio_seconds':.1,'rtf':2,'output_path':str(self.path),'output_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}]
        self.final = {'completed':1,'failed':0}

    def check(self, **kw):
        return audit(**({'expected_ids':['one'],'attempts':self.a,'generated':self.g,'final':self.final}|kw))

    def test_complete(self): self.assertTrue(self.check()['pass'])
    def test_missing_scheduled_job(self): self.assertFalse(self.check(expected_ids=['one','two'])['pass'])
    def test_failure_before_generation(self): self.assertFalse(self.check(attempts=self.a+[{'case_id':'two','ok':False,'exit_code':1}], expected_ids=['one','two'])['pass'])
    def test_hash_corruption(self):
        self.g[0]['output_sha256']='0'*64
        r=self.check();self.assertFalse(r['pass']);self.assertEqual(r['verified_audio_count'],0)
    def test_missing_hash(self):
        self.g[0].pop('output_sha256');self.assertFalse(self.check()['pass'])
    def test_silent_wav_with_valid_hash(self):
        with wave.open(str(self.path),'wb') as w:
            w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(bytes(8820))
        self.g[0]['output_sha256']=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertFalse(self.check()['pass'])
    def test_nonzero_exit_despite_generated(self):
        self.a[0]['exit_code']=1;self.assertFalse(self.check()['pass'])
    def test_missing_exit(self): self.assertFalse(self.check(attempts=[])['pass'])
    def test_empty_matrix(self): self.assertFalse(self.check(expected_ids=[])['pass'])
    def test_abort_with_completed_audio(self): self.assertFalse(self.check(aborted=True)['pass'])
    def test_missing_final(self): self.assertFalse(self.check(final=None)['pass'])
    def test_duplicate_retry(self): self.assertFalse(self.check(attempts=self.a+self.a)['pass'])
    def test_duplicate_generated(self): self.assertFalse(self.check(generated=self.g+self.g)['pass'])
    def test_cap(self):
        self.g[0]['hit_token_limit']=True;self.assertFalse(self.check()['pass'])
    def test_missing_file(self):
        self.path.unlink();self.assertFalse(self.check()['pass'])
    def test_malformed_log(self): self.assertFalse(self.check(parse_errors=['line 3 malformed'])['pass'])
    def test_bad_duration(self):
        self.g[0]['audio_seconds']=99;self.assertFalse(self.check()['pass'])


class AnalyzerIntegrationTests(EvidenceTests):
    """Invoke the actual CLI analyzer on isolated fixtures, not just the helper."""
    def check(self, **kw):
        import contextlib
        import importlib.util
        import io
        import types
        import yaml
        args = {'expected_ids':['one'],'attempts':self.a,'generated':self.g,'final':self.final}|kw
        root=Path(self.temp.name)/'repo';run=root/'results/fixture';(run/'logs').mkdir(parents=True,exist_ok=True);(run/'config').mkdir(exist_ok=True)
        (run/'config/manifest.json').write_text('{}')
        (run/'config/test-matrix.yaml').write_text(yaml.safe_dump({'cases':{'T0':{'clips':[{'case_id':x} for x in args['expected_ids']]}}}))
        rows=[dict(x,event='fish_clip_finished') for x in args['attempts']]+[dict(x,event='generated') for x in args['generated']]
        if args['final']: rows.append(dict(args['final'],event='fish_finished',t5_inserted=0))
        if args.get('aborted'): rows.append({'event':'fish_aborted'})
        text='\n'.join(json.dumps(x) for x in rows)
        if args.get('parse_errors'): text+='\nnot-json'
        (run/'logs/fish-runner.jsonl').write_text(text)
        path=Path(__file__).with_name('fish-s2-followup.py')
        spec=importlib.util.spec_from_file_location('fish_cli_fixture',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.ROOT=root
        with contextlib.redirect_stdout(io.StringIO()): code=mod.cmd_analyze(types.SimpleNamespace(run_id='fixture'))
        summary=json.loads((run/'summary.json').read_text());result=summary['integrity']
        self.assertEqual(code,0 if result['pass'] else 2)
        self.assertEqual(summary['acceptance_verdicts']['first_attempt_completion'].startswith('pass:'),result['pass'])
        return result


if __name__=='__main__': unittest.main()
