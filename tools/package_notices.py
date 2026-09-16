"""Stage dependency notices alongside private local build outputs."""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]

def stage_notices(destination):
    output = destination / 'licenses'
    roots = {'psxrecomp': ROOT/'psxrecomp', 'recomp-ui': ROOT/'recomp-ui'}
    for platform in ('build-macos', 'build-windows'):
        for path in (ROOT/platform/'_deps').glob('*-src'):
            roots[platform+'-'+path.name] = path
    if sys.platform == 'darwin':
        for name in ('sdl3','freetype','harfbuzz','glib','graphite2','pcre2','libpng',
                     'gettext','python@3.13','xz','mpdecimal','openssl@3','sqlite'):
            roots['homebrew-'+name] = (Path('/opt/homebrew/opt')/name).resolve()
    for label, root in roots.items():
        if not root.is_dir(): continue
        for path in root.rglob('*'):
            if '.git' in path.parts or not path.is_file(): continue
            name = path.name.upper()
            if not (name.startswith(('LICENSE','COPYING','NOTICE')) or name.endswith('.LICENSE')): continue
            if path.stat().st_size > 2_000_000: continue
            target = output/label/path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'LICENSE', output/'PROJECT-MIT.txt')
