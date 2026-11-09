import pocket_tts
import subprocess

text = 'Bonjour, ceci est un test.'

# Method 1: TTS class with to_file
try:
    from pocket_tts import TTS
    tts = pocket_tts.TTS()
    tts.to_file('Bonjour, ceci est un test.', '/tmp/test1.wav')
    print('Method 1 (TTS().to_file) succeeded')
except Exception as e:
    print('Method 1 failed: {}'.format(e))

# Method 2: generate function
try:
    from pocket_tts import generate
    generate('Bonjour, ceci est un test.', '/tmp/test2.wav')
    print('Method 2 (generate) succeeded')
except Exception as e:
    print('Method 2 failed: {}'.format(e))

# Method 3: CLI
try:
    result = subprocess.run(['pocket-tts', '--text', 'Bonjour', '--output', '/tmp/test3.wav'], capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        print('Method 3 (CLI) succeeded')
    else:
        print('Method 3 failed: {}'.format(result.stderr))
except Exception as e:
    print('Method 3 failed: {}'.format(e))

# Method 4: CLI help
try:
    result = subprocess.run(['pocket-tts', '--help'], capture_output=True, text=True, timeout=10)
    stdout = result.stdout[:500] if result.stdout else 'No stdout'
    stderr = result.stderr[:500] if result.stderr else 'None'
    print('CLI help: {}'.format(stdout))
    print('CLI stderr: {}'.format(stderr))
except Exception as e:
    print('Method 4 failed: {}'.format(e))