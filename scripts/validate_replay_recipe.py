"""Validate the native v2 recipe through real FastMCP tools on an owned test capture."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fastmcp import Client
from renderdoc_mcp.server.runtime import maybe_create_fastmcp


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-id', required=True)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--recipe', required=True)
    parser.add_argument('--dest', required=True)
    args = parser.parse_args()
    assert Path(args.capture).name == 'owned.rdc', 'Use the dedicated owned capture copy'
    recipe = json.loads(Path(args.recipe).read_text(encoding='utf-8-sig'))
    evidence = {}
    async with Client(maybe_create_fastmcp()) as client:
        async def call(name, **params):
            result = await client.call_tool(name, dict(window_id=args.window_id,
                                expected_capture=args.capture, **params))
            result = json.loads(result.content[0].text)
            assert result['ok'], result
            return result['data']
        async def settled():
            for _ in range(240):
                state = await call('get_replay_camera_state')
                if not any(state.get(k) for k in ('scanning','busy','pending_update')):
                    return state
                await asyncio.sleep(.5)
            raise AssertionError('Native operation timed out')
        before = await call('get_replay_camera_state')
        assert not before['enabled'] and before['active_pass_count'] == 0
        evidence['stored'] = await call('configure_replay_camera_recipe',recipe=recipe,run=False,show=True)
        assert evidence['stored']['field_count'] == before['field_count']
        assert evidence['stored']['recipe_passes_supported']
        bad = copy.deepcopy(recipe);bad['capture']['sha256'] = '0'*64
        await call('configure_replay_camera_recipe',recipe=bad,run=True)
        evidence['rejected'] = await settled()
        assert 'fingerprint' in evidence['rejected']['last_error']
        assert evidence['rejected']['field_count'] == before['field_count']
        assert not evidence['rejected']['enabled']
        await call('configure_replay_camera_recipe',recipe=recipe,run=True)
        evidence['scanned'] = await settled()
        assert not evidence['scanned']['last_error'], evidence['scanned']['last_error']
        assert evidence['scanned']['scan_partial'] and evidence['scanned']['recipe_result_ready']
        assert evidence['scanned']['scan_pass_count'] == len(recipe['passes'])
        assert not evidence['scanned']['enabled'] and evidence['scanned']['active_pass_count'] == 0
        evidence['accepted'] = await call('apply_replay_camera_recipe')
        evidence['applied'] = await settled()
        assert not evidence['applied']['last_error'], evidence['applied']['last_error']
        assert evidence['applied']['enabled'] and not evidence['applied']['panel_visible']
        assert evidence['applied']['active_pass_count'] == len(recipe['passes'])
        await call('reset_replay_camera')
        evidence['reset'] = await settled()
        assert not evidence['reset']['enabled'] and evidence['reset']['active_pass_count'] == 0
    Path(args.dest).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('PASS: FastMCP v2 recipe storage, fingerprint rejection, scan/report, explicit combined Apply, close, reset')


if __name__ == '__main__': asyncio.run(main())
