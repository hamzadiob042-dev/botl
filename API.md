# API — 3MH TECHNOLOGIES Python Remote Runner

الموقع: http://3mh.pages.dev · القناة: t.me/bshshshkk · الدعم: t.me/j49_c

هذا الملف يوثّق ثلاث واجهات:

1. **واجهة التنفيذ البعيدة** (بروتوكول WebSocket/Socket.IO الذي تتحدثه الأداة).
2. **خادم API المحلي** الذي تشغّله الأداة (`runner3mh.py serve`).
3. **واجهة بايثون البرمجية** (`import runner3mh`).

---

# أولاً — واجهة التنفيذ البعيدة

## 1. العنوان والترويسات

```
wss://repl.online-cpp.com/socket.io/?EIO=3&transport=websocket&type=script&lang=python3
```

| الترويسة | القيمة | ملاحظة |
|---|---|---|
| `Origin` | `https://www.online-python.com` | **إلزامية** — بدونها `403` أو `400 Origin not allowed` |
| `User-Agent` | متصفح حديث | مفضّلة |
| `Sec-WebSocket-Key/Version` | كما في RFC 6455 | تولّدها الأداة |

عنوان احتياطي: `wss://code-executor.online-cpp.com/socket.io/...`

البروتوكول: **Engine.IO v3 + Socket.IO v2** (النبض من جهة العميل).

| وسيط `type` | الوظيفة |
|---|---|
| `script` | تنفيذ ملفات (مع `lang=python3` أو `c` أو `cpp`) |
| `shell` | جلسة Python REPL تفاعلية |

## 2. تسلسل الجلسة

```
← 0{"sid":"...","upgrades":[],"pingInterval":25000,"pingTimeout":60000}   # Engine.IO open
→ 40                                                                       # Socket.IO connect
← 40
→ 42["code",[{"code":"print(1)","file_name":"main.py"}],"--n 5","main.py"]  # إطلاق التنفيذ
→ 42["message","<سطر stdin>"]                                              # فوراً (انظر §4)
← 42["ready","Environment ready"]
← 451-["output",{"_placeholder":true,"num":0}]                             # ترويسة مرفق ثنائي
← <إطار ثنائي> 0x04 || مخرجات UTF-8
← 42["exit","** Process exited - Return Code: 0 **",0]
→ 2   (كل 25 ثانية)      ← 3
```

### معاني رموز الحزم

| الرمز | المعنى |
|---|---|
| `0` / `1` / `2` / `3` / `4` | Engine.IO: open / close / ping / pong / message |
| `40` | Socket.IO connect |
| `42[...]` | حدث عادي (JSON) |
| `45<n>-[...]` | حدث ثنائي بانتظار `n` مرفقات |
| إطار ثنائي | أول بايت = نوع حزمة Engine.IO (`0x04`) وبقية البايتات = الحمولة |

### وسائط حدث `code`

| # | الوسيط | الشرح |
|---|---|---|
| 1 | `files` | `[{"code": str, "file_name": str}, ...]` — أسماء مسطّحة، كل الملفات في مجلد واحد |
| 2 | `arguments` | نص وسائط سطر الأوامر، يُجزّأ مثل shell ويُقصّ عند 500 حرف |
| 3 | `active` | اسم الملف المُنفَّذ — **الفارغ يعني ألا يُنفَّذ شيء** |

### أحداث الخادم

| الحدث | الحمولة |
|---|---|
| `ready` | `"Environment ready"` (مرتين عادة) |
| `output` | مرفق ثنائي (UTF-8) — stdout و stderr معاً في الغالب |
| `err` | مرفق ثنائي أو مصفوفة بايتات — stderr منفصل أحياناً |
| `exit` | `(رسالة، كود)` حيث `0` نجاح، `1000` = Killed، وغيره كود البرنامج |

## 3. فك ترميز المخرجات

`output`/`err` تصل بإحدى ثلاث صور، ويجب دعمها كلها:

```python
bytes                      # الإطار الثنائي بعد حذف بايت النوع 0x04
list[int]                  # مصفوفة بايتات داخل JSON
str                        # نص مباشر
```

## 4. سلوك stdin (الأهم)

في وضع `script` يسلّم الخادم للبرنامج **فقط** رسائل `message` الواصلة قبل بدء العملية:

| زمن الإرسال بعد `code` | النتيجة |
|---|---|
| 0.00s | يصل |
| ≥ 0.15s | يُتجاهل ⇒ يبقى البرنامج معلّقاً على `input()` |

لذا ترسل الأداة كل أسطر stdin مباشرة بعد `code`.
في وضع `shell` (REPL) يعمل الإدخال لحظياً بشكل طبيعي.

## 5. الحدود

| الحد | القيمة |
|---|---|
| المخرجات | 2MB ⇒ `exit 1000` ورسالة `Output Size exceeded 2MB. Process Killed.` |
| حجم الكود | ~600KB يعمل، ~1MB مرفوض |
| الزمن | لم يُرصد قتل قبل 175 ثانية |
| النبض | `pingInterval=25000ms`, `pingTimeout=60000ms` ⇒ يجب ping من العميل |
| الشبكة | محجوبة داخل بيئة التنفيذ |
| إعادة استخدام الجلسة | ممكنة: أكثر من `code` على نفس الاتصال |

## 6. واجهة الحفظ (HTTP)

```
POST https://www.online-python.com/Ide/share_code
Content-Type: application/x-www-form-urlencoded
Origin: https://www.online-python.com
X-Requested-With: XMLHttpRequest

code_content=[{"code":"...","file_name":"main.py","active":1}]&exp_days=30&lang=python3
→ {"output":true,"share_id":"U3ku0sIyJj","ci_csrf_token":null}
```

```
POST https://www.online-python.com/Ide/get_code
code_id=U3ku0sIyJj
→ {"output":true,"code":"[{\"code\": \"...\", \"file_name\": \"main.py\", \"active\": 1}]","lang":"python3"}
```

رابط المشاركة = `https://www.online-python.com/<share_id>`. لا حاجة إلى توكن CSRF.

## 7. ما لا يعمل

| المحاولة | النتيجة |
|---|---|
| `transport=polling` | المصافحة تنجح ثم تُقتل الجلسة: `400 {"code":1,"message":"Session ID unknown"}` |
| `Origin` مختلف أو مفقود | `403` / `400 Origin not allowed` |
| `EIO=4` | مرفوض — الخادم v3 فقط |
| `active=""` | لا يُنفَّذ شيء |
| `portal.online-python.com:8443` | يقبل TLS ثم لا يرد |

> ملاحظة: رسالة `Origin not allowed` تظهر أحياناً بشكل متقطع حتى مع ترويسة صحيحة، والحل هو
> إعادة المحاولة (`--retries`) مع التبديل إلى الخادم الاحتياطي.

---

# ثانياً — خادم API المحلي

```bash
runner3mh.py serve --bind 127.0.0.1 --port 8377
```

## `GET /health`

```json
{"status": "ok", "website": "http://3mh.pages.dev"}
```

## `GET /info`

```json
{
  "environment": {"python": "3.12.12", "implementation": "CPython", "platform": "Linux-...",
                  "machine": "x86_64", "working_directory": "/home/repl123", "user": "repl123", "cpus": 4},
  "modules": ["numpy==2.3.5", "pandas==2.3.3"],
  "limits": {"max_output_bytes": 2097152, "max_upload_bytes": 786432,
             "outbound_network": false, "killed_exit_code": 1000},
  "website": "http://3mh.pages.dev", "support": "t.me/j49_c"
}
```

## `POST /run`

| الحقل | النوع | الافتراضي | الشرح |
|---|---|---|---|
| `code` | string | — | كود مباشر (يُستخدم إن لم تُرسل `files`) |
| `files` | array | — | `[{"code","file_name","binary"?}, ...]` |
| `active` | string | `main.py` أو أول `.py` | الملف المُنفَّذ |
| `args` | string | `""` | وسائط سطر الأوامر (≤ 500 حرف) |
| `stdin` | array[string] | `[]` | أسطر تُسلَّم قبل بدء التنفيذ |
| `timeout` | number | `120` | مهلة بالثواني |
| `lang` | string | `python3` | `python3` / `c` / `cpp` |

```bash
curl -s http://127.0.0.1:8377/run -H 'Content-Type: application/json' \
  -d '{"code":"a=input();b=input();print(int(a)+int(b))","stdin":["20","22"],"timeout":30}'
```

```json
{"stdout":"42\n","stderr":"","exit_code":0,"exit_message":"** Process exited - Return Code: 0 **",
 "elapsed":0.21,"killed":false,"timed_out":false,"session_id":"abc...",
 "ok":true,"local_exit_code":0}
```

## `POST /share`

| الحقل | النوع | الافتراضي |
|---|---|---|
| `code` / `files` | كما في `/run` | — |
| `active` | string | تلقائي |
| `days` | int | `30` (مقيّد 1..365) |
| `lang` | string | `python3` |

```json
{"share_id":"hOKf9Tqc3v","url":"https://www.online-python.com/hOKf9Tqc3v"}
```

## أكواد HTTP

| الكود | الحالة |
|---|---|
| `200` | نجاح |
| `400` | حمولة غير صالحة، اسم ملف غير آمن، أو خطأ تنفيذ |
| `404` | مسار غير معروف |
| `413`-معاملة `400` | حجم أكبر من 3MB |
| `502` | تعذّر الوصول إلى الخادم البعيد |

الحماية: الاستماع على `127.0.0.1` فقط افتراضياً، حد أقصى للحجم 3MB، تعقيم أسماء الملفات
ورفض اجتياز المسار، ولا يوجد أي تنفيذ أوامر على الجهاز المضيف.

---

# ثالثاً — واجهة بايثون البرمجية

```python
import runner3mh
```

## الثوابت (CONFIG)

`EXECUTION_HOST`, `FALLBACK_EXECUTION_HOST`, `SITE_URL`, `SHARE_ENDPOINT`, `CODE_ENDPOINT`,
`SOCKET_PATH`, `REQUEST_ORIGIN`, `USER_AGENT`, `ENGINEIO_VERSION`, `DEFAULT_LANGUAGE`,
`DEFAULT_TIMEOUT`, `CONNECT_RETRIES`, `PING_INTERVAL`, `MAX_OUTPUT_BYTES`, `MAX_UPLOAD_BYTES`,
`MAX_ARGUMENT_CHARS`, `MAX_API_PAYLOAD_BYTES`, `KILLED_EXIT_CODE`, `LOCAL_TIMEOUT_CODE`,
`LOCAL_KILLED_CODE`, `SHARE_EXPIRY_DAYS`, `API_BIND_HOST`, `API_BIND_PORT`, `WEBSOCKET_GUID`,
`VERIFY_TLS`, `PROJECT_WEBSITE`, `SUPPORT_CHANNEL`, `SUPPORT_CONTACT`, `BANNER`

## الدوال

| الدالة | التوقيع | الوظيفة |
|---|---|---|
| `run_python_code` | `(code, arguments="", stdin_lines=(), timeout=120, language="python3", on_output=None, on_error=None, host=EXECUTION_HOST) -> ExecutionResult` | تنفيذ نص كود |
| `run_python_files` | `(files, active=None, arguments="", stdin_lines=(), timeout=120, language="python3", on_output=None, on_error=None, connection=None, host=EXECUTION_HOST) -> ExecutionResult` | تنفيذ قائمة ملفات (مع إعادة استخدام `connection`) |
| `collect_project_files` | `(paths=(), directories=()) -> list[dict]` | جمع الملفات من مسارات ومجلدات |
| `read_source_file` | `(path) -> dict` | قراءة ملف (نصّي أو ثنائي base64) |
| `resolve_active_file` | `(files, requested=None) -> str` | تحديد نقطة الدخول |
| `prepare_execution_payload` | `(files, active) -> (list[dict], str)` | تجهيز الحمولة وحقن الملفات الثنائية |
| `resolve_stdin_lines` | `(text=None, path=None, piped=True) -> list[str]` | تجميع أسطر الإدخال |
| `open_executor` | `(mode="script", language="python3", host=EXECUTION_HOST, retries=3) -> SocketConnection` | فتح جلسة مع إعادة محاولة وخادم احتياطي |
| `fetch_environment_info` | `(language="python3") -> dict` | فحص البيئة البعيدة |
| `share_code` | `(files, days=30, language="python3", active=None) -> str` | حفظ وإرجاع `share_id` |
| `fetch_shared_code` | `(share_id) -> (list[dict], str)` | جلب كود مشارك |
| `save_shared_code` | `(share_id, directory=".") -> (list[str], str)` | حفظه على القرص بمسارات معقّمة |
| `start_remote_repl` | `(language="python3", delay=0.5, grace=2.0, host=EXECUTION_HOST) -> int` | REPL تفاعلي |
| `watch_files` | `(paths, directories=(), active=None, arguments="", stdin_lines=(), interval=1.5, timeout=120, ...) -> int` | مراقبة وإعادة تشغيل |
| `serve_api` | `(host=API_BIND_HOST, port=API_BIND_PORT) -> int` | تشغيل خادم API المحلي |
| `start_interactive_menu` | `(host=EXECUTION_HOST, language="python3") -> int` | القائمة التفاعلية |
| `local_exit_code` | `(result) -> int` | تحويل كود الخروج البعيد إلى 0..255 |
| `print_status` | `(result, quiet=False) -> None` | سطر الحالة الملوّن |

## `ExecutionResult`

```python
@dataclass(slots=True)
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int | None
    exit_message: str
    elapsed: float
    killed: bool
    timed_out: bool
    session_id: str

    succeeded -> bool          # exit_code == 0 and not timed_out
    as_dict() -> dict          # + ok + local_exit_code
```

## `SocketConnection`

| العضو | الوظيفة |
|---|---|
| `session_id` | معرّف الجلسة البعيدة |
| `emit(event, *args)` | إرسال حدث Socket.IO |
| `read_event(timeout=3.0)` | `(name, args)` أو `None`، ويرسل ping تلقائياً |
| `close()` | إغلاق الجلسة |

## الاستثناءات

`RunnerError` ← `TransportError` ← `SocketClosed`

## مثال كامل

```python
import runner3mh

files = runner3mh.collect_project_files([], ["project"])
conn = runner3mh.open_executor()
for _ in range(3):
    r = runner3mh.run_python_files(files, "main.py", "--fast", ["in1", "in2"],
                                   timeout=60, connection=conn, on_output=print)
    print(r.exit_code, r.elapsed, r.succeeded)
conn.close()
print(runner3mh.SITE_URL + runner3mh.share_code(files, days=7))
```

---

**3MH TECHNOLOGIES** — http://3mh.pages.dev · t.me/bshshshkk · t.me/j49_c
