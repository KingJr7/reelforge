import pocket_tts
print('Pocket-TTS version:', pocket_tts.__version__ if hasattr(pocket_tts, '__version__') else 'unknown')
print('All attributes:', [x for x in dir(pocket_tts) if not x.startswith('_')])
import inspect
for name in dir(pocket_tts):
    if not name.startswith('_'):
        obj = getattr(pocket_tts, name)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                print('  {}{}'.format(name, sig))
            except:
                print('  {}: callable'.format(name))
        else:
            print('  {}: {}'.format(name, type(obj)))