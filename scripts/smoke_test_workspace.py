"""Explicit real-service smoke test. Never runs as part of pytest.

Connectivity: python scripts/smoke_test_workspace.py
Full pipeline: python scripts/smoke_test_workspace.py --paper path/to/paper.pdf
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from time import monotonic, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.application import Application


def wait(app, timeout=600):
    deadline = monotonic() + timeout
    while app.busy:
        if monotonic() >= deadline:
            raise TimeoutError('Workspace operation timed out')
        sleep(.1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--paper', type=Path)
    parser.add_argument('--question', default='请从知识库概括这篇论文的主要贡献，并提供引用。')
    args = parser.parse_args()
    if not os.getenv('DEEPSEEK_API_KEY'):
        print(json.dumps({'status':'blocked','reason':'DEEPSEEK_API_KEY is not configured'}))
        return 2
    with tempfile.TemporaryDirectory(prefix='cowork-live-') as folder:
        app = Application(folder)
        report = {'provider':'DeepSeek', 'model':app.agent.llm_client.model_name}
        try:
            app.probe_dependencies()
            wait(app)
            report['connection'] = app.get_status()['probe']
            if args.paper:
                job = app.submit_import([(args.paper.name, args.paper.read_bytes())])
                wait(app)
                report['import_status'] = app.get_job(job)['status']
                if report['import_status'] != 'completed':
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 1
                report['modes'] = {}
                for mode in ('rag','agent'):
                    c = app.create_conversation(mode)
                    run = app.start_turn(c['conversation_id'], args.question)
                    wait(app)
                    answer = app.get_conversation(c['conversation_id'])['messages'][-1]
                    report['modes'][mode] = {'status':app.read_events(run)['status'], 'citations':len(answer['citations']), 'latency_ms':answer['latency_ms'], 'error':answer['error']}
                identifier = app.list_documents()[0]['document_id']
                app.delete_document(identifier)
                wait(app)
                report['delete_verified'] = not app.list_documents() and not app.rag.retriever.retrieve('paper')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            passed = report['connection']['llm'] == '检查通过'
            if args.paper:
                passed = passed and report['delete_verified'] and all(x['status']=='completed' and x['citations']>0 for x in report['modes'].values())
            return 0 if passed else 1
        finally:
            app.close()

if __name__ == '__main__':
    raise SystemExit(main())
