# Third-party notices

AirControl depends on third-party software. The following report is generated from the Python and npm dependency manifests. Each component remains under its own license; consult its upstream license and notices for full terms.

## Python

Generated with `pip-licenses` from a clean environment installed from `requirements.txt`.

| Package | Version | License | Project |
|---|---:|---|---|
| aiohappyeyeballs | 2.7.1 | Python Software Foundation License | [aio-libs](https://github.com/aio-libs/aiohappyeyeballs) |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | [aio-libs](https://github.com/aio-libs/aiohttp) |
| aiosignal | 1.4.0 | Apache Software License | [aio-libs](https://github.com/aio-libs/aiosignal) |
| attrs | 26.1.0 | MIT | [attrs](https://www.attrs.org/) |
| colorama | 0.4.6 | BSD License | [colorama](https://github.com/tartley/colorama) |
| frozenlist | 1.8.0 | Apache-2.0 | [aio-libs](https://github.com/aio-libs/frozenlist) |
| idna | 3.20 | BSD-3-Clause | [idna](https://github.com/kjd/idna) |
| multidict | 7.2.1 | Apache-2.0 | [multidict](https://github.com/aio-libs/multidict) |
| Pillow | 12.3.0 | MIT-CMU | [Pillow](https://python-pillow.github.io/) |
| propcache | 0.5.4 | Apache-2.0 | [aio-libs](https://github.com/aio-libs/propcache) |
| pynput | 1.8.2 | GNU Lesser General Public License v3 (LGPLv3) | [pynput](https://github.com/moses-palmer/pynput) |
| pystray | 0.19.5 | GNU Lesser General Public License v3 (LGPLv3) | [pystray](https://github.com/moses-palmer/pystray) |
| qrcode | 8.2 | BSD License; Other/Proprietary License | [python-qrcode](https://github.com/lincolnloop/python-qrcode) |
| six | 1.17.0 | MIT License | [six](https://github.com/benjaminp/six) |
| typing_extensions | 4.16.0 | PSF-2.0 | [typing_extensions](https://github.com/python/typing_extensions) |
| yarl | 1.25.1 | Apache-2.0 | [aio-libs](https://github.com/aio-libs/yarl) |

Regenerate with: `python -m piplicenses --format=markdown --with-urls`.

## JavaScript and Android

Generated with `license-checker` from the production npm dependency tree.

- [@aparajita/capacitor-secure-storage 8.0.1](https://github.com/aparajita/capacitor-secure-storage) — MIT
- [@capacitor-community/keep-awake 8.0.1](https://github.com/capacitor-community/keep-awake) — MIT
- [@capacitor-mlkit/barcode-scanning 8.2.1](https://github.com/capawesome-team/capacitor-mlkit) — Apache-2.0
- [@capacitor/android 8.5.3](https://github.com/ionic-team/capacitor) — MIT
- [@capacitor/app 8.1.2](https://github.com/ionic-team/capacitor-plugins) — MIT
- [@capacitor/core 8.5.3](https://github.com/ionic-team/capacitor) — MIT
- [@capacitor/ios 8.5.3](https://github.com/ionic-team/capacitor) — MIT
- [@capacitor/keyboard 8.0.6](https://github.com/ionic-team/capacitor-keyboard) — MIT
- [@capacitor/preferences 8.0.1](https://github.com/ionic-team/capacitor-plugins) — MIT
- [@capacitor/screen-orientation 8.0.2](https://github.com/ionic-team/capacitor-plugins) — MIT
- [tslib 2.8.1](https://github.com/Microsoft/tslib) — 0BSD

Regenerate from the project root with: `npx license-checker --production --markdown`.

The license labels are scanner output, not legal advice. Verify upstream license files, especially for LGPL and dual-license dependencies, before redistributing packaged builds.

## Google ML Kit

The Android barcode-scanning plugin uses Google's scanner module and Google Play Services. Google's applicable terms and service documentation apply in addition to this project's license.
