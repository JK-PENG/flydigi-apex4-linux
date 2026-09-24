# Third-party notices

## openflydigi

Project: <https://github.com/mkaliaha/openflydigi>

Reference commit: `8477300f1bd0cdd0e4a277a544aa9b151c623e62`

Copyright: 2026 Mikalai Kaliaha

License: MIT

This repository already vendors `apex4ds5/_ds5/` from openflydigi. The adaptive
trigger work additionally adapts the DualSense report translation design and
game-specific mapping from these MIT files:

- `flydigi/ds5.py`
- `flydigi/effects.py`
- `flydigi/relay.py`
- `flydigi/identity.py`
- `flydigi/device.py`

The vendored DualSense codec's inputtino attribution remains in
`apex4ds5/_ds5/NOTICE`.

```text
MIT License

Copyright (c) 2026 Mikalai Kaliaha

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## ApexSenseBridge research reference

Project: <https://github.com/ReynArts/ApexSenseBridge>

Reviewed revision: `80e61fa1743106e92429ce1018b2ab8bfc49a9ae`

License: GPL-3.0-or-later

ApexSenseBridge was consulted only as public evidence that retail APEX 4
DeviceTypes 84 and 103 accept the old-protocol `0xA0` ForceAdapt frame over
wired and 2.4 GHz connections, and that resistance/reset work physically. No
GPL source was copied, ported, linked, imported or mechanically rewritten into
this MIT repository. The Linux packet builder and transport were independently
implemented from the recorded protocol facts and covered by exact-byte tests.

## Proton diagnostics research (2026-09-13)

Valve Wine at `b8fdff8e1f855b5276ec4ddca0f31b2792554322` was consulted to
verify environment-variable names, VID/PID syntax and their filtering behavior.
No Wine LGPL implementation is copied into the launcher.
`tools/windows-hid-probe.c` is an independent MIT implementation using the
documented Windows SetupAPI/HID APIs and this project's existing mild/Off byte
vectors. Microsoft's API documentation and Proton issue #5900 were research
references; no source from the external compatibility-check application was
copied. MinGW-w64 or Zig is a development-only toolchain; no compiler is bundled
with the Python relay.
