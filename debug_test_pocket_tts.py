import pocket_tts
import subprocess
import inspect

# 1. Check CLI subcommands
print("=== CLI subcommands ===")
try:
    result = subprocess.run(['pocket-tts', '--help'], capture_output=True, text=True, timeout=10)
    print(result.stdout)
except Exception as e:
    print('Failed:', e)

# 2. Inspect TTSModel more deeply
print("\n=== TTSModel details ===")
print('TTSModel:', pocket_tts.TTSModel)
print('TTSModel.__init__ signature:')
try:
    sig = inspect.signature(pocket_tts.TTSModel.__init__)
    print('  ', sig)
except Exception as e:
    print('  Failed:', e)

# 3. Check models module
print("\n=== pocket_tts.models ===")
print('Attributes:', [x for x in dir(pocket_tts.models) if not x.startswith('_')])

# 4. Check utils.config
print("\n=== pocket_tts.utils.config ===")
print('Attributes:', [x for x in dir(pocket_tts.utils.config) if not x.startswith('_')])

# 5. Try to see if there's a from_pretrained or similar
print("\n=== TTSModel methods ===")
for name in dir(pocket_tts.TTSModel):
    if not name.startswith('_'):
        obj = getattr(pocket_tts.TTSModel, name)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                print('  {}{}'.format(name, sig))
            except:
                print('  {}: callable'.format(name))
        else:
            print('  {}: {}'.format(name, type(obj)))

# 6. Check data module
print("\n=== pocket_tts.data ===")
print('Attributes:', [x for x in dir(pocket_tts.data) if not x.startswith('_')])

# 7. Try CLI with generate subcommand if exists
print("\n=== Testing CLI generate ===")
try:
    result = subprocess.run(['pocket-tts', 'generate', '--help'], capture_output=True, text=True, timeout=10)
    print('STDOUT:', result.stdout)
    print('STDERR:', result.stderr)
except Exception as e:
    print('Failed:', e)