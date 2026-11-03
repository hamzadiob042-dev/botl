# 3MH TECHNOLOGIES — Python Remote Runner

| | |
|---|---|
| الموقع | http://3mh.pages.dev |
| القناة | t.me/bshshshkk |
| الدعم والمطوّر | t.me/j49_c |

أداة واحدة (ملف بايثون واحد، **بدون أي مكتبات خارجية**) تشغّل ملفات ومشاريع بايثون على خادم تنفيذ بعيد عبر WebSocket، مع: قائمة تفاعلية، وضع REPL، خادم API محلي، مراقبة ملفات، مشاركة وسحب أكواد، ووضع برمجي (import) كامل.

---

## التثبيت

```bash
python3 runner3mh.py --help          # يتطلب Python 3.10+ (يفضّل 3.12)
chmod +x runner3mh.py
ln -s "$PWD/runner3mh.py" /usr/local/bin/runner3mh
```

لا يوجد `pip install` — كل شيء داخل `runner3mh.py` (عميل WebSocket و Engine.IO/Socket.IO مكتوبان من الصفر بالمكتبة القياسية).

---

## 1) القائمة التفاعلية

```bash
python3 runner3mh.py            # بدون أي وسيط ⇒ القائمة
python3 runner3mh.py menu
```

```
  1) تشغيل ملفات أو مشروع
  2) تشغيل كود مباشر
  3) جلسة REPL بعيدة
  4) مشاركة كود والحصول على رابط
  5) سحب كود من رابط مشاركة
  6) معلومات البيئة البعيدة
  7) تشغيل خادم API محلي
  0) خروج
```

كل خيار يسألك عما يحتاجه فقط (مسارات، وسائط، stdin، مهلة).

---

## 2) أوامر الطرفية

```bash
runner3mh.py run main.py                          # ملف واحد
runner3mh.py run -d project                       # مشروع كامل (كل ملفات المجلد)
runner3mh.py run main.py utils.py data.csv --active main.py
runner3mh.py run -c "print(sum(range(101)))"      # كود مباشر
runner3mh.py main.py                              # اختصار: run ضمنية
runner3mh.py run main.py --args "--n 5 --debug"   # وسائط البرنامج (sys.argv)
printf '3\n4\n' | runner3mh.py run calc.py        # تمرير stdin
runner3mh.py run calc.py --stdin "3\n4"
runner3mh.py run calc.py --stdin-file input.txt
runner3mh.py run main.py --json                   # نتيجة JSON
runner3mh.py run main.py --timeout 300 --save-output out.txt
runner3mh.py repl                                 # REPL بعيد تفاعلي
runner3mh.py watch main.py --interval 1.5         # إعادة تشغيل عند كل تعديل
runner3mh.py share main.py --days 30              # رابط مشاركة
runner3mh.py pull <share_id|url> -o ./out         # سحب كود مشارك
runner3mh.py info --json                          # تفاصيل البيئة البعيدة
runner3mh.py serve --bind 127.0.0.1 --port 8377   # خادم API محلي
```

خيارات عامة لكل الأوامر: `--host` `--lang` `--retries` `--insecure` `--json` `-q/--quiet`.

### أكواد الخروج

| الكود | المعنى |
|---|---|
| `0` | نجاح |
| `1..255` | كود خروج البرنامج البعيد |
| `137` | الخادم قتل العملية (تجاوز حد المخرجات 2MB) |
| `124` | انتهت المهلة المحلية |
| `2` | خطأ اتصال أو استخدام |
| `130` | إيقاف بـ Ctrl+C |

---

## 3) خادم API المحلي (HTTP/JSON)

```bash
runner3mh.py serve --port 8377
```

| الطلب | الوظيفة |
|---|---|
| `GET /health` | فحص الخادم |
| `GET /info` | معلومات البيئة البعيدة والمكتبات والحدود |
| `POST /run` | تنفيذ كود أو ملفات |
| `POST /share` | حفظ الكود وإرجاع رابط مشاركة |

```bash
curl -s http://127.0.0.1:8377/run -H 'Content-Type: application/json' \
     -d '{"code":"print(6*7)","args":"--x 1","stdin":["3","4"],"timeout":60}'

curl -s http://127.0.0.1:8377/run -d '{"files":[
  {"code":"from h import hi\nprint(hi())","file_name":"main.py"},
  {"code":"def hi(): return \"multi-ok\"","file_name":"h.py"}],"active":"main.py"}'

curl -s http://127.0.0.1:8377/share -d '{"code":"print(1)","days":7}'
```

استجابة `/run`:

```json
{"stdout":"42\n","stderr":"","exit_code":0,"exit_message":"** Process exited - Return Code: 0 **",
 "elapsed":0.24,"killed":false,"timed_out":false,"session_id":"...","ok":true,"local_exit_code":0}
```

الخادم يستمع على `127.0.0.1` افتراضياً (لا يعرّضه للشبكة)، ويرفض أي حمولة أكبر من 3MB، ويعقّم أسماء الملفات ضد اجتياز المسار.

---

## 4) الاستخدام البرمجي (Python API)

```python
import runner3mh

result = runner3mh.run_python_code("print('hi')", arguments="--n 5", timeout=60)
print(result.stdout, result.exit_code, result.succeeded, result.elapsed)
print(result.as_dict())

files = runner3mh.collect_project_files([], ["project"])
active = runner3mh.resolve_active_file(files)
runner3mh.run_python_files(files, active, on_output=print)

info = runner3mh.fetch_environment_info()
link = runner3mh.share_code(files, days=30)
saved, lang = runner3mh.save_shared_code(link, "out_dir")

conn = runner3mh.open_executor()
for _ in range(3):
    runner3mh.run_python_files(files, active, connection=conn)
conn.close()

runner3mh.start_remote_repl()
runner3mh.serve_api(port=8377)
```

الدوال العامة: `run_python_code`, `run_python_files`, `collect_project_files`, `read_source_file`,
`resolve_active_file`, `prepare_execution_payload`, `resolve_stdin_lines`, `open_executor`,
`fetch_environment_info`, `share_code`, `fetch_shared_code`, `save_shared_code`,
`start_remote_repl`, `watch_files`, `serve_api`, `start_interactive_menu`, `local_exit_code`,
`print_status` — والكائنات `ExecutionResult`, `SocketConnection`, `WebSocket`, `ApiHandler`.

---

## 5) حدود البيئة البعيدة (مقيسة عملياً)

| البند | القيمة |
|---|---|
| بايثون | 3.12.12 (CPython) على Debian 13 — 4 معالجات |
| المخرجات | 2MB كحد أقصى ثم يُقتل التشغيل (`exit 1000`) |
| حجم الكود المرفوع | ~600KB مضمون، ~1MB مرفوض |
| المكتبات | numpy 2.3.5، pandas 2.3.3، sqlalchemy + المكتبة القياسية |
| الإنترنت داخل البيئة | محجوب (لا `pip install` ولا requests) |
| بنية الملفات | مسطّحة — لا مجلدات فرعية |
| stdin | يُسلَّم **قبل** بدء العملية فقط (الأداة ترسله فوراً تلقائياً) |
| مهلة الجلسة | تحتاج ping كل 25 ثانية — الأداة ترسله تلقائياً |

---

## 6) ملاحظات أمنية

* التحقق من شهادات TLS مفعّل افتراضياً؛ `--insecure` للاختبار فقط.
* أسماء الملفات تُعقّم (`basename` + رفض `.`/`..`/`\x00`) عند الرفع وعند السحب، ومسار الحفظ يُتحقق منه بـ `commonpath`.
* لا يوجد أي تنفيذ أوامر shell محلياً، ولا `eval`/`exec`، ولا `pickle`/`yaml`.
* خادم API يربط على العنوان المحلي فقط، ويحدّ حجم الحمولة، ويرفض الملفات ذات المسارات غير الآمنة.
* SHA-1 مستخدم فقط في مصافحة WebSocket كما يفرض RFC 6455 (ليس لتشفير أو لأسرار).

---

## 7) الاختبار

```bash
python3 tests/smoke_test.py       # 17 اختباراً حياً ضد الخادم
```

---

## 8) الاستخدام المسؤول

الخدمة البعيدة مجانية وعامة ومملوكة لطرف ثالث، وقد يتغيّر بروتوكولها دون إشعار.
لا تستخدمها للأحمال الكثيفة أو في الإنتاج، ولا ترفع أكواداً ضارّة.
للاستخدام الثقيل شغّل بايثون محلياً.

**3MH TECHNOLOGIES** — http://3mh.pages.dev · t.me/bshshshkk · t.me/j49_c
