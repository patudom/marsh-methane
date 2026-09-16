# CH4 feedback model + CONUS warming maps

Two layers, both dependency-free ES modules, both validated against Python
references.

| Directory | What it is | Docs |
|---|---|---|
| `bundle/` | The coupled CH4 ↔ temperature feedback model. Global. | [bundle/README.md](bundle/README.md) |
| `map/` | CONUS maps by pattern scaling, plus WorldWide Telescope image sets. | [map/README.md](map/README.md) |

```bash
npm run validate       # bundle: 335/335  (JS vs Python, worst diff 7.4e-8)
npm run validate:map   # map:     49/49
npm run example        # CLI demo of the feedback model
```

```js
import { run, runDecomposed } from './bundle/ch4feedback.js';
import { createMapper }       from './map/ch4map.js';
```

**Two things to carry into any UI you build on this.** The methane feedback is
*damped*, not runaway — amplification is 1.05× even above the top of AR6's
assessed range, because warming also shortens CH4's lifetime. And the **CONUS
pattern is synthetic**: it is not derived from CMIP6 output, `map.isSynthetic`
says so, and `map/derive_pattern_from_cmip6.py` is the path to replacing it.

Python-side scripts, their dependencies and the WorldWide Telescope workflow
are documented in the two READMEs above.
