# DocBotRerollCookierun

เอกสารนี้สรุประบบปัจจุบันของโปรเจกต์ `Bot_reroll_cookierunV4` เพื่อให้ผู้ใช้หรือ AI ตัวอื่นอ่านต่อและแก้ระบบได้โดยไม่ต้องไล่เดา flow จากศูนย์

## ภาพรวม

โปรเจกต์นี้เป็นบอท reroll CookieRun บน MuMu Player โดยสั่งงานผ่าน `adb` และใช้ OpenCV สำหรับ screenshot, template matching, coordinate picker และ flow ที่ตัดสินใจจากภาพ

ระบบปัจจุบันมี 2 ชั้นหลัก:

1. `Bot.py` เก็บ step, group, state group และฟังก์ชันยิงคำสั่ง ADB
2. `Gui.py` เป็น GUI หลักแบบ `customtkinter` สำหรับรันหลาย device, debug step, score flow, pet image test, image matching และ Discord webhook notification

## ไฟล์สำคัญ

### `Bot.py`

หน้าที่หลัก:

- เก็บ `STEPS` ทั้งหมดแบบ 0-based index
- แบ่ง `STEPS` เป็น `STEP_GROUPS`
- รองรับ group ซ้อน group ผ่าน key `"groups"`
- กำหนด `MAIN_FLOW` สำหรับปุ่ม Run Full Flow
- ยิงคำสั่ง `tap`, `text`, `keyevent` ผ่าน ADB
- เพิ่ม jitter พิกัดและ delay runtime เพื่อให้การกดไม่ตายตัวเกินไป

ค่าคงที่สำคัญ:

```python
DEVICE_ID = "127.0.0.1:16384"
TAP_POSITION_JITTER = 2
DELAY_EXTRA_SECONDS_MIN = 0.0
DELAY_EXTRA_SECONDS_MAX = 2.0
```

รูปแบบ step:

```python
("tap", x, y, delay_seconds, "description")
("text", "some text", delay_seconds, "description")
("keyevent", "KEYCODE_ENTER", delay_seconds, "description")
```

หมายเหตุ:

- `delay_seconds` คือค่ารอพื้นฐาน
- ตอน runtime จะบวก delay สุ่มเพิ่มระหว่าง `0.0-2.0` วินาทีผ่าน `get_runtime_step_delay`
- `tap` จะถูก jitter พิกัดไม่เกิน `2` px ผ่าน `jitter_tap_coordinates`
- comment `# index xx` ใน `STEPS` ใช้สำหรับช่วยทำ slice ของ group ควรตรวจซ้ำหลังเพิ่ม/ลบ step

ฟังก์ชันสำคัญ:

```python
resolve_group_steps(group_key)
get_steps_for_flow(group_keys=None)
get_step_label(step, index=None)
jitter_tap_coordinates(x, y)
get_runtime_step_delay(step)
execute_step(device_id, step)
run_once(device_id)
```

### `STEP_GROUPS`

`STEP_GROUPS` มีทั้งกลุ่มที่ชี้ตรงไปยัง slice ของ `STEPS` และกลุ่ม state ที่รวมหลาย group ย่อย

กลุ่มพื้นฐานปัจจุบัน:

```python
reset_account             -> STEPS[0:5]
devplay_login             -> STEPS[5:8]
exit_tutorial             -> STEPS[8:11]
name_character            -> STEPS[11:15]
skip_news                 -> STEPS[15:18]
claim_popup_rewards       -> STEPS[18:28]
mailbox_rewards           -> STEPS[28:33]
enter_treasure_draw       -> STEPS[33:35]
open_treasure_boxes       -> STEPS[35:53]
exit_treasure             -> STEPS[51:53]
open_treasure_boxs_6+1    -> STEPS[53:64]
Hatch_9_time              -> STEPS[64:86]
Hatch_15_time             -> STEPS[86:120]
```

กลุ่ม state ปัจจุบัน:

```python
State_Reset_ID
State_Open_Free_Treasure
State_Open_Treasure_6+1
State_Open_Pets_15
State_Open_Pets_9
```

ตัวอย่าง group ซ้อน:

```python
"State_Reset_ID": {
    "label": "State_Reset_ID",
    "groups": [
        "reset_account",
        "devplay_login",
        "exit_tutorial",
        "name_character",
        "skip_news",
        "claim_popup_rewards",
        "mailbox_rewards",
    ],
}
```

ถ้าจะเพิ่ม group ใหม่:

1. เพิ่ม step ใน `STEPS`
2. ตรวจเลข index
3. เพิ่ม entry ใน `STEP_GROUPS`
4. ถ้าเป็น state รวมหลาย group ให้ใช้ `"groups"` แทน `"steps"`
5. ถ้าต้องการให้ Run Full Flow ใช้ด้วย ให้เพิ่ม key ใน `MAIN_FLOW`

### `MAIN_FLOW`

`MAIN_FLOW` คือ flow หลักสำหรับ `Run Full Flow`

```python
MAIN_FLOW = [
    "reset_account",
    "devplay_login",
    "exit_tutorial",
    "name_character",
    "skip_news",
    "claim_popup_rewards",
    "mailbox_rewards",
    "enter_treasure_draw",
    "open_treasure_boxes",
    "exit_treasure",
]
```

## `Gui.py`

GUI ปัจจุบันใช้ `customtkinter` ไม่ใช่ `ttk` เป็นหลักแล้ว

หน้าที่หลัก:

- รองรับสูงสุด `6` device slots
- มีแท็บ `Main`, `Config` และ `Debug`
- มี per-device Score Target เป็น `2` หรือ `3`
- มีปุ่ม `Run Score` และ `Stop` ราย device
- มีปุ่ม global เช่น `Run Full Flow`, `Run Score Flow`, `Run Pet Img Test`, `Stop All`
- มี `Main Log` พร้อม filter ตาม device
- มี Tab `Config` สำหรับปรับค่า step runtime และตั้งค่า Discord Webhook
- มี Discord Webhook ในแท็บ `Config` สำหรับแจ้งเตือนผลลัพธ์สำคัญ
- มี Debug log แบบเต็ม
- มี Coordinate Picker และ Capture Once
- มี Group/Single Step runner สำหรับ debug

ค่าคงที่สำคัญ:

```python
MAX_DEVICE_SLOTS = 6
IMAGE_SELECT_DIR = Path(__file__).resolve().parent / "Image_Select"
DISCORD_WEBHOOK_CONFIG_PATH = Path(__file__).resolve().parent / "discord_webhook.local"
STEP_CONFIG_PATH = Path(__file__).resolve().parent / "step_config.local"
DISCORD_WEBHOOK_TIMEOUT = 4
IMAGE_MATCH_THRESHOLD = 0.84
SCORE_MATCH_THRESHOLD = 0.84
MATCH_SCALES = (0.90, 0.95, 1.0, 1.05, 1.10)
SCORE_CHECK_ATTEMPTS = 5
SCORE_CHECK_RETRY_DELAY = 0.5
PET_CHECK_ATTEMPTS = 8
SCORE_TARGET_CHOICES = ("2", "3")
DEFAULT_SCORE_TARGET = 3
```

### GUI Layout

แท็บ `Main`:

- Device Settings แบบสรุป
- แต่ละ device slot มีช่อง device id, status, target score, Run Score, Stop
- Main Log
- filter Main Log เป็น `All Devices` หรือราย device

แท็บ `Config`:

- Step Config สำหรับเลือก step แล้วแก้ค่า runtime ผ่าน GUI
- ปุ่ม `Select` แสดงรายการ step แบบ inline scroll list ในหน้าเดิม ไม่เปิด popup window แยก
- รายการ step แสดงสูงประมาณ 10 แถวและเลื่อนเลือกได้
- ช่อง `Step Text` ใช้แก้ description/note ของ step
- ช่อง `Text Value` แสดงเฉพาะ step ประเภท `text` เช่น `13. [text] Input name`
- สำหรับ step ประเภท `tap` แก้ค่า `X`, `Y`, `Time` ได้
- สำหรับ step ประเภท `text` แก้ค่า `Text Value`, `Step Text`, `Time` ได้
- สำหรับ step ประเภท `keyevent` แก้ค่า `Step Text` และ `Time` ได้
- ปุ่ม `Save Step` บันทึกค่าลง runtime และไฟล์ `step_config.local`
- ปุ่ม `Reload` โหลดค่าล่าสุดของ step นั้นกลับเข้า UI ใช้ยกเลิกค่าที่พิมพ์ค้างก่อนกด Save
- Notifications สำหรับวาง Discord Webhook URL, Save และ Test

แท็บ `Debug`:

- Coordinate Picker
- Bot Control
- Step Control
- Group และ Single Step ใช้ปุ่ม `Select` แสดงรายการแบบ inline scroll list สูงประมาณ 10 แถว ไม่เปิด popup window แยก
- Debug Log

### Step Config

`Config > Step Config` ใช้ปรับค่าของ `STEPS` จาก GUI โดยไม่ต้องแก้ `Bot.py` ตรง ๆ

ค่าที่ปรับได้:

```text
tap      -> x, y, time, step text
text     -> text value, time, step text
keyevent -> time, step text
```

เมื่อกด `Save Step` ระบบจะ:

1. อัปเดต tuple ใน `STEPS`
2. อัปเดต `STEP_GROUPS` ที่อ้าง tuple เดิมจาก slice ของ `STEPS`
3. อัปเดตรายการเลือก step ใน `Config` และ `Debug`
4. บันทึก override ลงไฟล์ local

ไฟล์ config:

```text
step_config.local
```

รายละเอียด:

- ไฟล์นี้อยู่ข้าง `Gui.py`
- ถูก ignore ด้วย rule `*.local` ใน `.gitignore`
- เก็บเฉพาะค่าที่แก้ผ่าน GUI เช่น `x`, `y`, `time`, `note`, `value`
- ตอนเปิด GUI ระบบจะโหลด override จากไฟล์นี้แล้ว apply ทับ `STEPS` ใน memory
- ถ้าต้องการกลับไปใช้ค่าใน `Bot.py` ให้ลบ entry ในไฟล์นี้หรือถอดไฟล์ `step_config.local` ออก
- Console bot (`python Bot.py`) ไม่โหลด `step_config.local`; override นี้มีผลกับ GUI runtime เท่านั้น

### Discord Webhook

Webhook เป็น optional ถ้าไม่กรอก URL ระบบจะไม่ส่ง notification และ bot ทำงานเหมือนเดิม

การตั้งค่าใน GUI:

1. เปิดแท็บ `Config`
2. วาง Discord webhook URL ใน section `Notifications`
3. กด `Save`
4. กด `Test` เพื่อทดสอบส่งข้อความไป Discord

ไฟล์ config:

```text
discord_webhook.local
```

รายละเอียด:

- ไฟล์นี้อยู่ข้าง `Gui.py`
- ถูก ignore ด้วย rule `*.local` ใน `.gitignore`
- ไม่ควร commit หรือส่งไฟล์นี้ให้คนอื่น เพราะ webhook URL ใช้ส่งข้อความเข้า channel ได้
- ถ้าล้างช่อง URL แล้วกด `Save` ระบบจะลบ config local

ระบบส่ง webhook ด้วย standard library:

```python
urllib.request
```

ไม่มี dependency เพิ่มใน `requirements.txt`

Event ที่ส่ง notification:

- `BotRunner`: เจอ select image หลังเปิดกล่อง และหยุด runner
- `ScoreFlowRunner`: score ถึง target score แล้วจบ flow
- `PetImageTestRunner`: เจอ pet target แล้วหยุดเพื่อเก็บ account

ข้อควรระวัง:

- ส่งแบบ background thread เพื่อไม่ให้ GUI หรือ bot flow ค้าง
- มี timeout `4` วินาที
- ถ้าส่งไม่สำเร็จจะแสดง warn ใน log แต่ไม่หยุด bot
- ไม่ส่งทุก cycle เพื่อลด spam และลดโอกาสชน Discord rate limit

## Runner ใน `Gui.py`

### `BotRunner`

ใช้สำหรับรัน step แบบทั่วไป:

- `Run Full Flow`
- `Run Group`
- `Run Step`

ลักษณะ:

- รับ `steps`, `run_label`, `loop_enabled`
- รันบน thread แยกต่อ device
- delay ถูกแบ่ง sleep ทีละ `0.1` วินาที ทำให้ stop ได้ระหว่างรอ
- ถ้าเจอ select image หลัง `Press Open Supreme boxs...` จะหยุด runner
- ถ้าตั้งค่า Discord webhook ไว้ จะส่ง notification ตอนเจอ select image

### `ScoreFlowRunner`

ใช้กับ `Run Score Flow` หรือปุ่ม `Run Score` ราย device

หน้าที่:

- นับคะแนนจาก target image
- เปลี่ยน state ตามคะแนน
- หยุดเมื่อคะแนนถึง target score ของ device นั้น
- target score เลือกได้ `2` หรือ `3`
- ถ้า reset account แล้วเริ่มรอบใหม่ คะแนนจะ reset เป็น `0`
- ถ้าตั้งค่า Discord webhook ไว้ จะส่ง notification ตอน score complete

Target image:

```python
Victor'sFeatherLaurelWreath
Jingle-jangleCoinWallet
TaterTraderhatched!
```

ชื่อเดียวกันนับได้ครั้งเดียวใน account เดียว เพื่อกันการนับซ้ำจาก popup เดิม

State routing:

```text
เริ่ม -> State 1: State_Open_Free_Treasure

ถ้าหลัง State 1 score == 2:
    -> State 3: State_Open_Pets_15
    -> ถ้ายังไม่ครบ target score -> State 6: State_Reset_ID

ถ้าหลัง State 1 score == 0 หรือ 1:
    -> State 2: State_Open_Treasure_6+1
    -> ถ้าหลัง State 2 score == 2:
        -> State 5: State_Open_Pets_9
    -> ถ้ายังไม่ครบ target score -> State 6: State_Reset_ID

ถ้าระหว่างทาง score >= target score:
    -> หยุด device นั้น
```

### `PetImageTestRunner`

ใช้กับ `Run Pet Img Test`

หน้าที่:

- ทดสอบหา `TaterTraderhatched!`
- รัน `State_Open_Pets_15`
- ถ้าเจอภาพ pet target จะหยุดและเก็บ account ปัจจุบันไว้
- ถ้าไม่เจอ จะรัน `State_Reset_ID` แล้ววนใหม่
- ถ้าตั้งค่า Discord webhook ไว้ จะส่ง notification ตอนเจอ pet target

## Image Matching

ระบบใช้ OpenCV `matchTemplate` แต่ปรับให้เสถียรกว่า template matching ธรรมดา:

- อ่าน PNG ด้วย `np.fromfile + cv2.imdecode` เพื่อรองรับ path/filename บน Windows
- crop template จากกรอบ marker
- รองรับ marker สีเขียว `#26E600` และกรอบแดงแบบเดิม
- ใช้ grayscale matching
- ทดลองหลาย scale จาก `MATCH_SCALES`
- เก็บ score ต่อ part ของ template

### โฟลเดอร์ภาพ

โครงสร้างปัจจุบัน:

```text
Image_Select/
  Pets/
    Definitions/
      TaterTraderhatched!.png
    Additional/
      ...
  Treasure/
    Definitions/
      Jingle-jangleCoinWallet.png
      Victor'sFeatherLaurelWreath.png
    Additional/
      ...
```

### Score Templates

`load_score_templates()` โหลดเฉพาะไฟล์ที่ `stem` อยู่ใน `SCORE_TARGET_STEMS`

```python
SCORE_TARGET_STEMS = {
    "Victor'sFeatherLaurelWreath",
    "Jingle-jangleCoinWallet",
    "TaterTraderhatched!",
}
```

`Additional` ยังไม่ได้นับคะแนนโดยตรง เว้นแต่ชื่อไฟล์ตรงกับ target stems ที่กำหนด

### Tater Trader Matching

`TaterTraderhatched!` มี policy พิเศษ:

```python
TARGET_MATCH_THRESHOLDS = {
    "TaterTraderhatched!": 0.82,
}

MULTI_PART_MATCH_TARGETS = {
    "TaterTraderhatched!": {
        "required_parts": 4,
        "min_average_score": 0.90,
    },
}
```

ความหมาย:

- แต่ละ part ของ template ต้องผ่าน threshold
- ต้องผ่านอย่างน้อย `4` parts
- ค่าเฉลี่ยต้อง >= `0.90`
- ลด false positive จากภาพ pet อื่นที่คล้ายกัน

## Coordinate Picker

มี 2 จุด:

1. `CoordPicker.py` เป็น standalone script
2. `Gui.py` มีปุ่ม `Find Position`

การใช้งาน:

- left-click แสดงพิกัด
- right-click ส่ง tap จริง
- `SPACE` pause/resume
- `q` ออก

หมายเหตุ: Coordinate picker และ Capture Once ใช้ device ตัวแรกที่กรอกไว้ ไม่ได้เปิดพร้อมกันหลายเครื่อง

## Dependency

มี `requirements.txt` แล้ว:

```text
numpy>=1.26
opencv-python>=4.9
customtkinter>=5.2
```

Discord webhook ใช้ `urllib.request` จาก Python standard library จึงไม่ต้องติดตั้ง package เพิ่ม

สิ่งที่ต้องมีนอก Python:

- ADB ที่เรียกจาก command line ได้
- MuMu Player เปิดใช้งาน
- device id เช่น `127.0.0.1:16384`

ไฟล์ช่วย:

```text
install_dependencies.bat
run_gui.bat
Setup.md
```

## วิธีรัน

ติดตั้ง dependency:

```powershell
pip install -r requirements.txt
```

หรือใช้:

```powershell
install_dependencies.bat
```

รัน GUI:

```powershell
python Gui.py
```

หรือ:

```powershell
run_gui.bat
```

รัน console bot:

```powershell
python Bot.py
```

รัน coordinate picker standalone:

```powershell
python CoordPicker.py
```

ตรวจ device:

```powershell
adb devices
```

## จุดที่มักต้องแก้

### เพิ่ม step

แก้ `STEPS` ใน `Bot.py`

```python
("tap", 640, 520, 3.0, "Press Some Button"),  # index xx
```

หลังเพิ่มต้องตรวจ:

- index comment
- slice ใน `STEP_GROUPS`
- state group ที่เกี่ยวข้อง
- `MAIN_FLOW` ถ้าต้องการให้ Run Full Flow ใช้ด้วย
- ถ้ามี `step_config.local` อยู่และ index ที่เพิ่ม/ลบทำให้ตำแหน่ง step เปลี่ยน ควรตรวจไฟล์ override นี้ด้วย เพราะ key อ้างอิงด้วย step index แบบ 0-based

### ปรับ step ผ่าน GUI

ถ้าแก้แค่พิกัด, delay, text value หรือ description ของ step เดิม ให้ใช้:

```text
Config > Step Config > Select > Save Step
```

แนวทาง:

- ใช้ `Select` เลือก step จาก inline list
- แก้ `X`, `Y`, `Time` สำหรับ step ประเภท `tap`
- แก้ `Text Value` สำหรับ step ประเภท `text`
- แก้ `Step Text` เพื่อเปลี่ยนชื่อ/คำอธิบายที่แสดงใน log และ selector
- กด `Save Step` เพื่อบันทึกลง `step_config.local`
- กด `Reload` ถ้าต้องการยกเลิกค่าที่พิมพ์ไว้แต่ยังไม่ได้ save

### เพิ่ม group

ถ้า group อ้าง slice:

```python
"new_group": {
    "label": "New Group",
    "steps": STEPS[120:125],
}
```

ถ้า group รวมหลาย group:

```python
"State_New": {
    "label": "State_New",
    "groups": [
        "group_a",
        "group_b",
    ],
}
```

### เพิ่ม target image

ถ้าต้องการให้เป็น score target:

1. วาง PNG ใน `Image_Select/.../Definitions`
2. ใส่กรอบ marker รอบส่วนที่ต้อง match
3. เพิ่ม stem ใน `SCORE_TARGET_STEMS`
4. ถ้าต้องการชื่อสั้นใน log ให้เพิ่มใน `SCORE_TARGET_SHORT_NAMES`
5. ถ้าภาพ false positive ง่าย ให้เพิ่ม policy ใน `TARGET_MATCH_THRESHOLDS` หรือ `MULTI_PART_MATCH_TARGETS`

### ปรับความแม่นของ matching

จุดที่แก้ได้ใน `Gui.py`:

```python
SCORE_MATCH_THRESHOLD
MATCH_SCALES
SCORE_CHECK_ATTEMPTS
SCORE_CHECK_RETRY_DELAY
TARGET_MATCH_THRESHOLDS
MULTI_PART_MATCH_TARGETS
```

แนวทาง:

- ไม่เจอทั้งที่ควรเจอ: ลด threshold หรือเพิ่ม scale
- เจอผิดภาพ: เพิ่ม threshold หรือใช้ multi-part policy
- ภาพขึ้นช้า: เพิ่ม attempts หรือ retry delay

## ข้อจำกัด

- Step ยังอิงพิกัดหน้าจอและ delay เป็นหลัก
- Image matching ยังเป็น template matching ไม่ใช่ OCR/AI vision
- ถ้า emulator resolution/scale เปลี่ยนมาก อาจต้องทำ template ใหม่
- ถ้า UI เกมเปลี่ยนหรือ popup แทรก flow อาจหลุด
- ADB command ส่วนใหญ่ยังไม่ได้ตรวจ `returncode`/`stderr` อย่างละเอียด
- Console bot (`Bot.py`) ไม่ใช้ GUI score flow
- Console bot (`Bot.py`) ไม่ใช้ `step_config.local`
- Discord webhook เป็น network call ภายนอก ถ้า URL ผิดหรือ Discord ช้า จะขึ้น warn ใน log แต่ไม่หยุด bot

## ตรวจหลังแก้

ควรรัน:

```powershell
python -m py_compile Bot.py Gui.py CoordPicker.py
```

ตรวจ group ที่สำคัญ:

```powershell
python -c "from Bot import resolve_group_steps; keys=['State_Open_Free_Treasure','State_Open_Treasure_6+1','State_Open_Pets_15','State_Open_Pets_9','State_Reset_ID']; print([(k, len(resolve_group_steps(k))) for k in keys])"
```

ตรวจ GUI import:

```powershell
python -c "import Gui; print('Gui import ok')"
```

ตรวจ GUI customtkinter smoke test:

```powershell
python -c "import customtkinter as ctk, Gui; ctk.set_appearance_mode('dark'); ctk.set_default_color_theme('blue'); root=ctk.CTk(); root.withdraw(); app=Gui.App(root); root.update_idletasks(); app.tab_view.set('Config'); root.update_idletasks(); app.tab_view.set('Debug'); root.update_idletasks(); app.tab_view.set('Main'); root.update_idletasks(); root.destroy(); print('ctk tab style ok')"
```

ตรวจ template:

```powershell
python -c "import Gui; print([(t['name'], t['file'], t['part'], t['size']) for t in Gui.load_score_templates()])"
```

## สรุปสำหรับ AI ที่จะทำงานต่อ

อ่านตามลำดับนี้:

1. `Bot.py`: ดู `STEPS`, `STEP_GROUPS`, state groups และ helper runtime
2. `Gui.py`: ดู constants, template loading, runners, UI methods
3. `Image_Select`: ดู target templates และ marker boxes
4. `requirements.txt` และ `Setup.md`: ดู dependency/setup

ถ้าจะแก้ flow ให้เริ่มจาก `STEP_GROUPS` และ `ScoreFlowRunner`

ถ้าจะแก้ matching ให้เริ่มจาก:

```python
extract_red_box_regions
load_score_templates
find_template_matches
TARGET_MATCH_THRESHOLDS
MULTI_PART_MATCH_TARGETS
```

ถ้าจะแก้ UI ให้ดู:

```python
App._build_main_tab
App._build_config_tab
App._build_step_config
App._build_debug_tab
App._build_device_settings
App._toggle_inline_picker
```

ถ้าจะแก้ Discord webhook ให้ดู:

```python
read_discord_webhook_url
write_discord_webhook_url
post_discord_webhook
App._build_notification_settings
App.notify_discord_result
```

ถ้าจะแก้ Step Config ให้ดู:

```python
read_step_config_overrides
write_step_config_overrides
App._load_step_config_overrides
App._load_config_step_fields
App._set_config_text_value_visible
App._replace_step_everywhere
App._refresh_step_selectors
App._on_save_config_step
```
