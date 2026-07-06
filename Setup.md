# Setup Guide

คู่มือนี้อธิบายขั้นตอนสำหรับคนที่ `git clone` โปรเจกต์นี้ไปใช้งานบนเครื่องใหม่ ตั้งแต่การเตรียมเครื่อง ติดตั้ง dependency เช็ก `adb` และรันโปรแกรม GUI

## 1. สิ่งที่ต้องมีในเครื่อง

ก่อน clone โปรเจกต์ ควรติดตั้ง/เตรียมสิ่งเหล่านี้ให้พร้อม:

- Git
- Python 3
- MuMu Player
- ADB ที่สามารถเรียกใช้จาก PowerShell หรือ Command Prompt ได้

เช็ก Python:

```powershell
py -3 --version
```

ถ้าขึ้นเวอร์ชัน เช่น `Python 3.12.x` แปลว่าใช้งานได้

## 2. Clone โปรเจกต์

เปิด PowerShell ในโฟลเดอร์ที่ต้องการเก็บโปรเจกต์ แล้วรัน:

```powershell
git clone <repo-url>
cd Bot_reroll_cookierunV4
```

คำอธิบาย:

- `git clone <repo-url>` คือการดาวน์โหลดโปรเจกต์จาก Git repository ลงมาไว้ในเครื่อง
- `cd Bot_reroll_cookierunV4` คือการเข้าไปในโฟลเดอร์โปรเจกต์ที่เพิ่ง clone มา

ให้เปลี่ยน `<repo-url>` เป็น URL จริงของ repository เช่น:

```powershell
git clone https://github.com/username/Bot_reroll_cookierunV4.git
```

## 3. ติดตั้ง Python dependency

หลังจากเข้าโฟลเดอร์โปรเจกต์แล้ว ให้รัน:

```powershell
.\install_dependencies.bat
```

ไฟล์นี้จะทำสิ่งต่อไปนี้ให้อัตโนมัติ:

- สร้าง virtual environment ชื่อ `.venv`
- อัปเกรด `pip`
- ติดตั้ง library จาก `requirements.txt`

dependency หลักของโปรเจกต์นี้คือ:

```text
numpy
opencv-python
```

ถ้าติดตั้งสำเร็จ จะมีโฟลเดอร์ `.venv` ถูกสร้างขึ้นในโปรเจกต์

## 4. เปิด MuMu Player

ก่อนเช็ก `adb` ให้เปิด MuMu Player และเปิด instance ที่ต้องการใช้งานก่อน

ถ้าใช้หลาย instance ให้เปิด instance ทั้งหมดที่ต้องการให้บอทควบคุม

## 5. เช็กว่า ADB ใช้งานได้ไหม

รันคำสั่งนี้ใน PowerShell:

```powershell
adb version
```

ถ้าใช้งานได้ จะเห็นข้อมูลเวอร์ชันของ Android Debug Bridge

ถ้าขึ้น error ประมาณนี้:

```text
adb is not recognized as an internal or external command
```

แปลว่า Windows ยังหา `adb.exe` ไม่เจอ หรือยังไม่ได้เพิ่ม ADB เข้า `PATH`

## 6. วิธีแก้เมื่อใช้คำสั่ง adb ไม่ได้

ให้ลองหา `adb.exe` ในเครื่องก่อน:

```powershell
where adb
```

ถ้าเจอ path แปลว่าเครื่องมี `adb` แล้ว เช่น:

```text
C:\platform-tools\adb.exe
```

หรืออาจเจอ path ของ MuMu เช่น:

```text
C:\Program Files\Netease\MuMu Player 12\shell\adb.exe
```

ถ้า `where adb` ไม่เจอ ให้ทำอย่างใดอย่างหนึ่ง:

1. ติดตั้ง Android Platform Tools แล้วเพิ่มโฟลเดอร์ที่มี `adb.exe` เข้า Windows `PATH`
2. ใช้ `adb.exe` ที่มากับ MuMu Player แล้วเพิ่มโฟลเดอร์นั้นเข้า Windows `PATH`
3. รัน `adb.exe` ด้วย path เต็มแทน เช่น:

```powershell
"C:\Program Files\Netease\MuMu Player 12\shell\adb.exe" devices
```

หลังแก้ PATH แล้ว ให้ปิด PowerShell เดิม เปิดใหม่ แล้วลอง:

```powershell
adb version
```

อีกครั้ง

## 7. เช็กว่า ADB เห็น MuMu Player หรือไม่

หลังจากเปิด MuMu Player แล้ว ให้รัน:

```powershell
adb devices
```

ถ้าเชื่อมต่อสำเร็จ ควรเห็น device ประมาณนี้:

```text
List of devices attached
127.0.0.1:16384    device
```

คำอธิบาย:

- `127.0.0.1:16384` คือ Device ID หรือ ADB port ของ MuMu instance
- `device` แปลว่าเชื่อมต่อสำเร็จและพร้อมใช้งาน

ถ้าไม่มี device แสดงขึ้นมา ให้ลอง connect เอง:

```powershell
adb connect 127.0.0.1:16384
adb devices
```

ถ้า port `16384` ใช้ไม่ได้ อาจเป็นเพราะ MuMu instance ใช้ port อื่น

## 8. วิธีลองหา port ของ MuMu

MuMu แต่ละ instance อาจใช้ port ไม่เหมือนกัน โดยเฉพาะเมื่อเปิดหลายจอ

ให้ลอง connect port ที่พบบ่อย:

```powershell
adb connect 127.0.0.1:16384
adb connect 127.0.0.1:16416
adb connect 127.0.0.1:16448
adb connect 127.0.0.1:16480
adb devices
```

ถ้าเจอ device แล้ว ให้นำค่าเช่น `127.0.0.1:16384` ไปใส่ในช่อง Device ID ของ GUI

## 9. รัน GUI

เมื่อ dependency พร้อม และ `adb devices` เห็น MuMu แล้ว ให้รัน:

```powershell
.\run_gui.bat
```

คำอธิบาย:

- `.\run_gui.bat` คือไฟล์สำหรับเปิดหน้า GUI ของบอท
- ถ้ามี `.venv` โปรแกรมจะใช้ Python จาก `.venv`
- ถ้าไม่มี `.venv` โปรแกรมจะลองใช้ `python Gui.py` แทน

หรือรันตรง ๆ ได้ด้วย:

```powershell
.venv\Scripts\python.exe Gui.py
```

## 10. ลำดับคำสั่งแบบสั้น

ใช้ลำดับนี้เมื่อ setup เครื่องใหม่:

```powershell
git clone <repo-url>
cd Bot_reroll_cookierunV4
.\install_dependencies.bat
adb version
adb devices
.\run_gui.bat
```

ถ้า `adb devices` ยังไม่เจอเครื่อง ให้แก้ ADB/port ให้เรียบร้อยก่อนค่อยรัน GUI

## 11. ปัญหาที่พบบ่อย

### adb is not recognized

สาเหตุ:

- ยังไม่ได้ติดตั้ง ADB
- ติดตั้งแล้ว แต่ไม่ได้เพิ่มเข้า Windows `PATH`

วิธีแก้:

- ติดตั้ง Android Platform Tools หรือใช้ ADB ที่มากับ MuMu
- เพิ่มโฟลเดอร์ที่มี `adb.exe` เข้า `PATH`
- เปิด PowerShell ใหม่ แล้วลอง `adb version`

### adb devices ไม่เห็น MuMu

สาเหตุ:

- ยังไม่ได้เปิด MuMu Player
- MuMu ใช้ ADB port อื่น
- ADB server ยังไม่เชื่อมกับ instance

วิธีแก้:

```powershell
adb connect 127.0.0.1:16384
adb devices
```

ถ้ายังไม่เจอ ให้ลอง port อื่น เช่น:

```powershell
adb connect 127.0.0.1:16416
adb connect 127.0.0.1:16448
adb connect 127.0.0.1:16480
adb devices
```

### GUI เปิดได้ แต่บอทไม่กดในเกม

สาเหตุที่เป็นไปได้:

- Device ID ใน GUI ไม่ตรงกับค่าที่เห็นจาก `adb devices`
- MuMu ยังไม่ได้อยู่หน้าจอที่บอทคาดไว้
- resolution หรือ scaling ของ emulator ไม่ตรงกับพิกัดที่ตั้งไว้ใน `Bot.py`

วิธีแก้:

- ใช้ Device ID จาก `adb devices`
- เปิดเกมให้อยู่สถานะเริ่มต้นที่ถูกต้อง
- ใช้ปุ่ม `Find Position` หรือ `CoordPicker.py` เพื่อหาและแก้พิกัดใหม่

