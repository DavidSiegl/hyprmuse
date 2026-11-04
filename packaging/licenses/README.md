# Native license texts

`packaging/third_party_notices.py` puts these in the binary's
`hyprmuse-third-party-licenses.txt`. They are the notices of code that no Python
distribution carries a license file for: the C libraries python-build-standalone links
into the interpreter, and those lxml's wheels link statically. Each file is copied
unchanged from the source named below, except `libiconv.txt` and `hacl.txt`, whose
first paragraphs say where in their sources the license was stated.

They were taken for Python 3.14.7 from python-build-standalone release `20260929`, the
build uv installs, and for lxml 6.0.2. The script refuses any other Python minor version
or lxml version (`NOTICED_PYTHON`, `NOTICED_LXML`).

| File | Source |
|---|---|
| `cpython.txt` | `lib/python3.14/LICENSE.txt` of the Python build |
| `cpython-incorporated.rst` | the "Licenses and Acknowledgements for Incorporated Software" section of CPython's `Doc/license.rst` at tag `v3.14.7` |
| `hacl.txt` | the license headers of CPython's `Modules/_hacl/` at tag `v3.14.7`, which has no license file |
| `openssl.txt`, `libffi.txt`, `expat.txt`, `sqlite.txt`, `bzip2.txt`, `liblzma.txt`, `mpdecimal.txt`, `libuuid.txt`, `ncurses.txt`, `libedit.txt` | `python/licenses/LICENSE.<name>.txt` in the release's `-full.tar.zst` archive (`openssl-3` for OpenSSL) |
| `zstd.txt` | `LICENSE` of facebook/zstd at `v1.5.7`, the version the build links; the archive names but lacks it |
| `zlib.txt` | `LICENSE` of madler/zlib at `v1.3.2`; Python links 1.3.2, lxml 1.3.1, under the same terms |
| `libxml2.txt` | `Copyright` of GNOME/libxml2 at `v2.14.6` |
| `libxslt.txt` | `Copyright` of GNOME/libxslt at `v1.1.43`, which covers libexslt too |
| `libiconv.txt` | `COPYING.LIB` of `libiconv-1.18.tar.gz` from ftp.gnu.org |

## Refreshing them

When the script refuses a build, or before raising either version:

1. Python: in the `-full.tar.zst` archive of the python-build-standalone release uv
   installs, `python/PYTHON.json` gives, under `build_info.extensions`, the libraries
   each extension module links and their license files. The modules that matter are
   those in `sys.builtin_module_names`, which the build links into `libpython`.
   Add or update a file for each such library, and `cpython*` from the new Python.
   PYTHON.json names external libraries only: also check the code CPython vendors
   under `Modules/` (such as `Modules/_hacl`) for licenses that `Doc/license.rst`
   does not list.
2. lxml: `lxml.etree.LIBXML_VERSION` and `LIBXSLT_VERSION` give two of the versions,
   `strings` on `lxml/etree.*.so` gives zlib's (`deflate x.y.z`), and the
   `_libiconv_version` symbol gives libiconv's as `0xMMmm`. Its `buildlibxml.py` lists
   what the wheels link.
3. Update `NATIVE_NOTICES`, `NOTICED_PYTHON` and `NOTICED_LXML` in the script, and this
   file.
