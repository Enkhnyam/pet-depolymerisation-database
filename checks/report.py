import html
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run import SCRIPTS

here = Path(__file__).parent
output = here.parent / "artifacts" / "checks_report.html"

sections = []
for relative_path in SCRIPTS:
    script = here / relative_path
    title = script.stem.replace("_", " ")
    group = script.parent.name.replace("_", " ")

    result = subprocess.run([sys.executable, str(script)], cwd=here, text=True,
                            capture_output=True,
                            env={**__import__("os").environ, "PYTHONPATH": str(here)})
    body = result.stdout if result.returncode == 0 else result.stdout + "\n" + result.stderr
    sections.append(f"""
      <section>
        <h2>{html.escape(title)}<span class="group">{html.escape(group)}</span></h2>
        <pre>{html.escape(body.strip())}</pre>
      </section>""")

navigation = "".join(
    f'<a href="#{i}">{html.escape(Path(p).stem.replace("_", " "))}</a>'
    for i, p in enumerate(SCRIPTS))
numbered = "".join(s.replace("<section>", f'<section id="{i}">')
                   for i, s in enumerate(sections))

output.write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Checks</title>
<style>
  body {{ font: 15px/1.6 -apple-system, system-ui, sans-serif; margin: 0;
          color:
  header {{ padding: 28px 40px; border-bottom: 1px solid
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  .when {{ color:
  nav {{ padding: 14px 40px; border-bottom: 1px solid
  nav a {{ display: inline-block; margin: 3px 12px 3px 0; font-size: 13px; color:
  main {{ padding: 8px 40px 60px; max-width: 1100px; }}
  section {{ margin: 34px 0; }}
  h2 {{ font-size: 17px; margin: 0 0 2px; }}
  .group {{ float: right; font-weight: normal; font-size: 12px; color:
            text-transform: uppercase; letter-spacing: .5px; }}
  .what {{ color:
  pre {{ background:
         padding: 14px 16px; overflow-x: auto; font-size: 13px; line-height: 1.45; }}
</style></head><body>
<header>
  <h1>Results, derived from the data</h1>
  <div class="when">{len(SCRIPTS)} checks &middot; generated {datetime.now():%d %B %Y, %H:%M}</div>
</header>
<nav>{navigation}</nav>
<main>{numbered}</main>
</body></html>""")

print(f"wrote {output}  ({len(SCRIPTS)} checks, {output.stat().st_size // 1024} KB)")
