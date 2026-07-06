# DocBotRerollCookierun

เอกสารนี้สรุปโครงสร้างและกระบวนการทำงานของโปรเจกต์ `Bot_reroll_cookierunV4` เพื่อให้ AI หรือนักพัฒนาคนอื่นเข้าใจระบบและทำงานต่อได้เร็ว

## ภาพรวมระบบ

โปรเจกต์นี้เป็นบอท reroll สำหรับเกม CookieRun ที่รันบน MuMu Player ผ่านคำสั่ง `adb` โดยใช้พิกัดหน้าจอแบบตายตัวเพื่อกดปุ่มตามลำดับที่กำหนดไว้ล่วงหน้า

ระบบมี 2 วิธีใช้งานหลัก:

1. รันบอทแบบ console ผ่าน `Bot.py`
2. รันผ่าน GUI ผ่าน `Gui.py` ซึ่งมีปุ่มควบคุมบอท, log, list devices, device slots สูงสุด 6 เครื่อง และเครื่องมือเลือกพิกัด

ไฟล์ `CoordPicker.py` เป็นเครื่องมือ standalone สำหรับจับภาพหน้าจอ emulator แบบ live เพื่อคลิกดูพิกัดหรือทดสอบ tap

## ไฟล์ในโปรเจกต์

### `Bot.py`

ไฟล์หลักของบอทแบบ command line

หน้าที่สำคัญ:

- กำหนด `DEVICE_ID = "127.0.0.1:16384"` เป็น device เริ่มต้นของ MuMu Player
- กำหนดรายการ action ทั้งหมดใน `STEPS`
- กำหนดตัวแปรแยกกลุ่มงานใหม่ใน `STEP_GROUPS` โดยยังเก็บ `STEPS` เดิมไว้ครบ
- กำหนดลำดับ flow หลักใน `MAIN_FLOW`
- ส่งคำสั่ง ADB เพื่อ `tap`, `input text`, และ `keyevent`
- รัน reroll เป็นรอบ ๆ แบบ infinite loop จนกด `Ctrl+C`

ฟังก์ชันหลัก:

- `tap(device_id, x, y)` ส่งคำสั่ง `adb shell input tap x y`
- `input_text(device_id, text)` ส่งคำสั่ง `adb shell input text ...`
- `keyevent(device_id, keycode)` ส่งคำสั่ง `adb shell input keyevent ...`
- `execute_step(device_id, step)` แปลง step แต่ละตัวเป็น action จริง
- `get_steps_for_flow(group_keys=None)` รวม step จาก group ตามลำดับที่ส่งเข้าไป หรือใช้ `MAIN_FLOW` ถ้าไม่ส่งค่า
- `get_step_label(step, index=None)` สร้างข้อความแสดง step สำหรับ GUI
- `run_once(device_id)` รัน `STEPS` ครบหนึ่งรอบ
- `main()` วนเรียก `run_once()` ไปเรื่อย ๆ

รูปแบบข้อมูลใน `STEPS`:

```python
("tap", x, y, delay_seconds, "description")
("text", "some text", delay_seconds, "description")
("keyevent", "KEYCODE_ENTER", delay_seconds, "description")
```

ค่า `delay_seconds` อยู่รองสุดท้ายเสมอ และ `description` อยู่ท้ายสุด

ตัวแปร flow ใหม่:

```python
STEP_GROUPS = {
    "reset_account": {"label": "Reset Account", "steps": STEPS[0:5]},
    ...
}

MAIN_FLOW = [
    "reset_account",
    "devplay_login",
    ...
]
```

กลุ่มใน `STEP_GROUPS` อ้างอิง slice จาก `STEPS` เดิม จึงควรระวัง index ถ้าเพิ่ม/ลบ step ใน `STEPS`

### `Gui.py`

ไฟล์ GUI หลัก ใช้ `tkinter` สำหรับหน้าจอควบคุม และใช้ `cv2`/`numpy` สำหรับ screenshot live

หน้าที่สำคัญ:

- ให้ผู้ใช้กรอก `Device ID`
- รองรับ device slot สูงสุด 6 ช่องสำหรับรันบอทหลาย emulator พร้อมกัน
- มีปุ่ม `Run Score` และ `Stop` แยกในแต่ละ device slot เพื่อเริ่ม/หยุด score flow รายเครื่อง
- แยกหน้าเป็นแท็บ `Main` และ `Debug`
- แท็บ `Main` แสดง Device Settings แบบย่อและ `Main Log` สำหรับดู loop/score รายเครื่อง
- แท็บ `Debug` เป็นหน้าควบคุมเดิมพร้อม Coordinate Picker, Bot Control, Step Control และ log เต็ม
- ปุ่ม `Fill Found Devices` สำหรับเติม device จาก `adb devices` ลง slot อัตโนมัติ
- ปุ่ม `List Devices` สำหรับรัน `adb devices`
- ปุ่ม `Find Position` เปิดหน้าต่าง live coordinate picker
- ปุ่ม `Capture Once` จับ screenshot ครั้งเดียว
- ปุ่ม `Run Bot` และ `Stop Bot` สำหรับควบคุม reroll
- ปุ่ม `Run Full Flow` สำหรับรันตาม `MAIN_FLOW`
- ปุ่ม `Run Score Flow` สำหรับรัน flow นับคะแนนจนเจอเป้าหมายครบ 3 คะแนน
- dropdown `Group` และปุ่ม `Run Group` สำหรับรันเฉพาะกลุ่ม step
- dropdown `Single Step` และปุ่ม `Run Step` สำหรับรัน step เดี่ยวเพื่อ debug
- ระหว่าง step เปิดกล่อง treasure ระบบจะตรวจภาพใน `Image_Select` หลัง delay ของคำสั่ง `Press Open Supreme boxs ...`
- checkbox `Loop` กำหนดว่าจะวนหลายรอบหรือรันครั้งเดียว
- แสดง log การทำงานบนหน้าจอ

ไฟล์นี้ import ข้อมูลและฟังก์ชันจาก `Bot.py`:

```python
from Bot import STEPS, STEP_GROUPS, MAIN_FLOW, get_steps_for_flow, get_step_label
```

ดังนั้นถ้าต้องแก้ลำดับ reroll หลัก ให้แก้ที่ `STEPS` และตรวจ `STEP_GROUPS`/`MAIN_FLOW` ใน `Bot.py` ให้ตรงกัน แล้ว GUI จะใช้ flow ใหม่อัตโนมัติ

กลไก thread:

- `BotRunner` 1 ตัวต่อ 1 device ใช้ background thread แยกกัน เพื่อให้รันพร้อมกันได้สูงสุด 6 device
- `BotRunner` รับ `steps`, `run_label`, และ `loop_enabled` ตอนเริ่มรัน ทำให้ใช้ runner เดียวกันได้ทั้ง full flow, group และ single step
- `BotRunner` จะหยุด step ถัดไปทันทีถ้า image matching เจอ PNG ใด ๆ ใน `Image_Select` หลังเปิดกล่อง treasure
- `ScoreFlowRunner` เป็น runner พิเศษสำหรับนับคะแนนจากภาพเป้าหมาย 3 รูป และเปลี่ยน flow ตามคะแนน
- `_coord_thread` รัน coordinate picker ใน background thread
- `_coord_window_running` เป็น global flag สำหรับสั่งหยุด coordinate picker

ข้อควรระวัง:

- Tkinter ไม่ได้ thread-safe เต็มรูปแบบ ควรอัปเดต UI ผ่าน `root.after(...)` เป็นหลัก
- ปุ่ม `Stop Bot` ใน GUI สามารถหยุดระหว่าง delay ได้ เพราะ delay ถูกแบ่ง sleep ทีละ `0.1` วินาที
- `Run Full Flow` ใช้ค่า checkbox `Loop` ได้ แต่ `Run Group` และ `Run Step` ตั้งใจให้รันครั้งเดียวเพื่อใช้ debug
- Coordinate picker และ `Capture Once` ยังใช้ device ตัวแรกที่กรอกไว้ ไม่ได้เปิดพร้อมกันหลายเครื่อง
- `Bot.py` แบบ console หยุดได้ด้วย `Ctrl+C` เท่านั้น

### Image Matching ในช่วงเปิดกล่อง

ไฟล์ PNG สำหรับเลือกผลลัพธ์ที่ต้องหยุดให้วางไว้ใน:

```text
Image_Select/
```

ระบบอ่านทุกไฟล์ `*.png` ในโฟลเดอร์นี้ และพยายามตัดพื้นที่ด้านในกรอบสีแดงออกมาเป็น template ก่อนนำไปเทียบกับ screenshot จริงผ่าน OpenCV `matchTemplate`

ค่าที่เกี่ยวข้องอยู่ใน `Gui.py`:

```python
IMAGE_SELECT_DIR = Path(__file__).resolve().parent / "Image_Select"
IMAGE_MATCH_THRESHOLD = 0.84
OPEN_BOX_STEP_PREFIX = "Press Open Supreme boxs"
```

เงื่อนไขทำงาน:

- หลัง step เช่น `("tap", 749, 522, 10.0, "Press Open Supreme boxs 1")` ยิง tap และรอครบ `10.0` วินาทีแล้ว
- GUI จะ capture screenshot ของ device นั้น
- ถ้าเจอ template ใด ๆ ใน `Image_Select` ด้วย score ตั้งแต่ `0.84` ขึ้นไป จะหยุด runner ของ device นั้นทันที
- ถ้าไม่เจอ จะทำ step ถัดไปตามปกติ เช่น confirm แล้วเปิดกล่องรอบถัดไป

### Score Flow

ปุ่ม `Run Score Flow` จะนับแต้มจากภาพเป้าหมายต่อ device จนครบ 3 คะแนนแล้วหยุด

ไฟล์เป้าหมายที่นับคะแนน:

```text
Image_Select/Treasure/Definitions/Victor'sFeatherLaurelWreath.png
Image_Select/Treasure/Definitions/Jingle-jangleCoinWallet.png
Image_Select/Pets/Definitions/TaterTraderhatched!.png
```

กติกา:

- เจอ `Victor'sFeatherLaurelWreath` ได้ `+1`
- เจอ `Jingle-jangleCoinWallet` ได้ `+1`
- เจอ `TaterTraderhatched!` ได้ `+1`
- ชื่อเดียวกันนับคะแนนได้ครั้งเดียว เพื่อกันการนับซ้ำจาก reward screen เดิม
- ถ้าคะแนนครบ `3/3` จะหยุด runner ของ device นั้น

ลำดับ flow:

1. เริ่มด้วย `enter_treasure_draw`
2. รัน `open_treasure_boxes`
3. ถ้าคะแนนรวมเป็น `0` หรือ `1` จะรัน `open_treasure_boxs_6+1`
4. ถ้าหลัง `open_treasure_boxs_6+1` คะแนนเป็น `2` จะรัน `Hatch_9_time`
5. ถ้าหลัง `open_treasure_boxes` คะแนนเป็น `2` ขึ้นไป จะรัน `Hatch_15_time`
6. ถ้ายังไม่ครบ `3` จะ reset account แล้วกลับมาถึง `enter_treasure_draw` ก่อนวนใหม่

กลุ่มที่ใช้ใน reset loop:

```python
RESET_TO_TREASURE_FLOW = [
    "reset_account",
    "devplay_login",
    "exit_tutorial",
    "name_character",
    "skip_news",
    "claim_popup_rewards",
    "mailbox_rewards",
    "enter_treasure_draw",
]
```

### `CoordPicker.py`

เครื่องมือ standalone สำหรับค้นหาพิกัดบนหน้าจอ MuMu Player

หน้าที่สำคัญ:

- ดึง screenshot ผ่าน `adb exec-out screencap -p`
- decode ภาพด้วย OpenCV
- เปิดหน้าต่าง live view
- left-click เพื่อ print พิกัด `x, y`
- right-click เพื่อส่ง tap จริงไปยัง emulator
- กด `SPACE` เพื่อ pause/resume ภาพ
- กด `q` เพื่อออก

ไฟล์นี้เหมาะสำหรับใช้ก่อนแก้ `STEPS` เพื่อหาพิกัดปุ่มใหม่หลัง UI เกมเปลี่ยน

## Dependency และเครื่องมือที่ต้องมี

โปรเจกต์นี้ไม่มีไฟล์ `requirements.txt` หรือ config dependency อื่นใน repository

สิ่งที่ต้องมีในเครื่อง:

- Python
- ADB ที่เรียกได้จาก `PATH`
- MuMu Player เปิดใช้งานและเชื่อมกับ ADB ได้
- Python packages:
  - `opencv-python` สำหรับ `cv2`
  - `numpy`

`tkinter`, `subprocess`, `threading`, `time`, และ `sys` เป็นส่วนที่มักมากับ Python หรือ standard library

คำสั่งตรวจ device:

```powershell
adb devices
```

ตัวอย่าง device ที่ระบบตั้งไว้:

```text
127.0.0.1:16384
```

ถ้า MuMu Player ใช้ port อื่น ให้แก้ `DEVICE_ID` ใน `Bot.py`/`CoordPicker.py` หรือกรอกผ่าน GUI ใน `Gui.py` ได้สูงสุด 6 ช่อง

## Flow การทำงานของบอท

ลำดับหลักอยู่ใน `STEPS` ของ `Bot.py` โดยครอบคลุมประมาณนี้:

1. เข้าเมนู setting
2. เข้า game info
3. ลบ account และรอโหลด
4. confirm การลบ
5. login ผ่าน DevPlay
6. ออกจากเกม/ข้าม tutorial
7. ใส่ชื่อตัวละคร
8. ปิด popup ข่าว/โฆษณา
9. รับของรางวัลรายวันและของขวัญ
10. เข้า mailbox
11. claim reward ทั้งหมด
12. ออกจาก mailbox
13. จบรอบ แล้วเริ่มรอบใหม่ถ้าอยู่ใน loop mode

ทุก step เป็นการกดตามพิกัดหน้าจอ จึงขึ้นกับ:

- resolution ของ emulator
- scaling ของ MuMu Player
- state ปัจจุบันของเกม
- เวลาโหลดของเครื่องและ network
- UI เกมหลังอัปเดต

ถ้าบอทกดผิดตำแหน่ง ให้ใช้ `CoordPicker.py` หรือปุ่ม `Find Position` ใน GUI เพื่อหาพิกัดใหม่ แล้วแก้ค่าใน `STEPS`

## วิธีรัน

รัน GUI:

```powershell
python Gui.py
```

รัน bot แบบ console:

```powershell
python Bot.py
```

รัน coordinate picker แบบ standalone:

```powershell
python CoordPicker.py
```

## จุดที่มักต้องแก้เมื่อต้องพัฒนาต่อ

### แก้ลำดับการกด

แก้ `STEPS` ใน `Bot.py`

ตัวอย่างเพิ่ม step tap:

```python
("tap", 640, 520, 3.0, "Press Some Button")
```

### แก้ชื่อที่กรอกในเกม

แก้ step นี้ใน `Bot.py`:

```python
("text", "MyCharacterName", 2.5, "Input name")
```

หมายเหตุ: `adb shell input text` มีข้อจำกัดกับช่องว่างและอักขระพิเศษ หากต้องกรอกชื่อซับซ้อนอาจต้อง escape text หรือใช้วิธี paste ผ่าน clipboard/IME เพิ่มเติม

### แก้ device เริ่มต้น

ใน `Bot.py`:

```python
DEVICE_ID = "127.0.0.1:16384"
```

ใน `CoordPicker.py`:

```python
DEVICE_ID = "127.0.0.1:16384"
```

ใน `Gui.py`:

```python
DEFAULT_DEVICE_ID = "127.0.0.1:16384"
```

### ปรับความเร็ว

แก้ delay ของแต่ละ step ใน `STEPS`

ถ้าเครื่องหรือ network ช้า ให้เพิ่ม delay หลัง step ที่มีโหลดหนัก เช่น delete account, login, tutorial, mailbox claim

## ข้อจำกัดของระบบปัจจุบัน

- ไม่มี image recognition หรือ state detection ระบบกดตามพิกัดและเวลารอเท่านั้น
- ถ้าเกมโหลดช้า, popup เปลี่ยน, หรือ UI เปลี่ยน บอทอาจหลุด flow
- ไม่มี error handling จาก `adb` อย่างละเอียด เพราะคำสั่งส่วนใหญ่ใช้ `capture_output=True` แต่ไม่ตรวจ `returncode`
- ไม่มี config แยก เช่น JSON/YAML สำหรับ `STEPS`
- ไม่มีระบบบันทึกผลลัพธ์ reroll หรือเช็คว่ารอบนั้นได้ตัวละคร/ไอเท็มที่ต้องการหรือไม่
- ไม่มี dependency file ทำให้ setup เครื่องใหม่อาจต้องเดา package เอง

## แนวทางพัฒนาต่อที่แนะนำ

1. แยก `STEPS`, `DEVICE_ID`, และชื่อ character ไปเป็น config file
2. เพิ่ม `requirements.txt`
3. เพิ่มการตรวจ `adb` error และแสดง stderr ใน log
4. ปรับ GUI logging ให้ thread-safe ทั้งหมดผ่าน `root.after(...)`
5. เพิ่มระบบ screenshot matching หรือ image recognition เพื่อตรวจ state ก่อนกด
6. เพิ่มปุ่ม pause/resume bot ใน GUI
7. เพิ่ม export/import step list เพื่อแก้ flow โดยไม่ต้องแก้โค้ด
8. เพิ่ม dry-run mode เพื่อ log action โดยไม่ยิงคำสั่ง adb จริง

## คำแนะนำสำหรับ AI ที่จะทำงานต่อ

ก่อนแก้โค้ดควรอ่านไฟล์ตามลำดับนี้:

1. `Bot.py` เพื่อเข้าใจ action list และ flow หลัก
2. `Gui.py` เพื่อเข้าใจ UI, threading, และการเรียกใช้ flow
3. `CoordPicker.py` เพื่อเข้าใจวิธีหาพิกัดและทดสอบ tap

ถ้าผู้ใช้ขอแก้พิกัดหรือเปลี่ยน flow ให้แก้ `STEPS` ใน `Bot.py` เป็นหลัก และตรวจว่า slice ใน `STEP_GROUPS` ยังแบ่งถูกกลุ่มหรือไม่

ถ้าผู้ใช้ขอปรับหน้าจอหรือปุ่มควบคุม ให้แก้ `Gui.py`

ถ้าผู้ใช้ขอปรับเครื่องมือหาพิกัด standalone ให้แก้ `CoordPicker.py`

หลังแก้ควรตรวจอย่างน้อย:

```powershell
python -m py_compile Bot.py Gui.py CoordPicker.py
```

และถ้ามี emulator พร้อมใช้งาน ควรทดสอบ:

```powershell
adb devices
python Gui.py
```

## สรุปสั้น

ระบบนี้เป็น ADB coordinate automation สำหรับ reroll CookieRun บน MuMu Player โดยมี `Bot.py` เป็นแหล่งความจริงของ flow, `Gui.py` เป็นหน้าควบคุมที่รองรับรันบอทพร้อมกันได้สูงสุด 6 device, และ `CoordPicker.py` เป็นเครื่องมือช่วยหาพิกัด การพัฒนาต่อควรระวังเรื่องพิกัดหน้าจอ, delay, device id, thread-safety ของ Tkinter และการตรวจ error จาก ADB
