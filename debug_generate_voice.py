#!/usr/bin/env python3
"""Debug script to test generate_voice_pocket_tts function directly."""

import sys
sys.path.insert(0, '.')

from make_reel import generate_voice_pocket_tts
from script_parser import parse_script

def main():
    with open('scripts/test_pocket_tts.txt', 'r') as f:
        script_text = f.read()
    
    parsed = parse_script(script_text)
    print(f'Parsed {len(parsed.words)} words')
    print(f'Words: {[w.text for w in parsed.words[:10]]}...')
    
    try:
        dur, wt = generate_voice_pocket_tts(parsed.clean_text, parsed.words, True)
        print(f'generate_voice_pocket_tts returned: duration={dur}, word_times={len(wt)}')
        if wt:
            print(f'First 5 word_times: {wt[:5]}')
        return 0
    except Exception as e:
        print(f'ERROR in generate_voice_pocket_tts: {e}')
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())