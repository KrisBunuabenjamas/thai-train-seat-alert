# แจ้งเตือนที่นอนรถไฟกลับมาว่าง

กรุงเทพอภิวัฒน์ → อุดรธานี วันที่ **29 และ 30 ธันวาคม 2026** ตรวจทุกประเภทตู้นอนในทุกขบวนที่ D-Ticket ส่งกลับ แล้วส่ง Discord เมื่อเต็ม → ว่าง เพื่อให้เปิดเว็บจองด้วยตัวเอง

**โค้ดพร้อมรันไม่ได้หมายความว่าเปิดเฝ้าตรวจแล้ว** ต้องตั้งค่า Secret, initialize state, ทดสอบข้อความ และเปิด MONITOR_ENABLED ตามขั้นตอนด้านล่าง

## พฤติกรรม

- ตั้งรอบ GitHub Actions ทุก 5 นาที เริ่มนาที 02, 07, 12 ฯลฯ; GitHub อาจรันช้าหรือข้ามรอบ จึงไม่รับประกันว่าจะทันที่นั่งที่หลุดช่วงสั้น ๆ
- พบว่างครั้งแรกแจ้งทันทีหลังตรวจ; ยังว่างต่อเนื่องไม่ส่งซ้ำ แม้จำนวนว่างเพิ่ม
- กลับมาเต็มแล้วว่างอีกครั้งจะแจ้งใหม่
- แสดงกลุ่มตู้ให้ชัด รวมตู้ผู้พิการ/สตรีและเด็กด้วย ผู้จองต้องมีคุณสมบัติตรงกับตู้
- API ไม่บอกเหตุผลที่ว่าง จึงไม่ได้ยืนยันว่าเป็นการยกเลิกทุกครั้ง
- เว็บ error/ข้อมูลหายจะไม่เปลี่ยนเป็น FULL; ผิดพลาด 3 รอบติดจะแจ้งปัญหา 1 ครั้งและแจ้งเมื่อกลับมาปกติ
- เก็บคิวก่อนส่ง เมื่อ Discord ล้มเหลวจะตรวจใหม่ก่อนส่งรอบหน้า ถ้าที่นั่งเต็มไปแล้วจะยกเลิกข้อความค้างนั้น
- ไม่จองหรือกันที่นั่งอัตโนมัติ; ไม่มี Firebase และไม่ต้องใช้บัญชี D-Ticket
- ตัดแต่ละขบวนเมื่อถึงเวลาออกตามเวลาไทย; หลัง 30 ธ.ค. ไม่มีการเรียก D-Ticket อีก ให้ปิด workflow เมื่อจบการเดินทางเพื่อไม่ให้เกิด run ที่ไม่จำเป็น

## เปิดใช้บน GitHub

1. นำโค้ดขึ้น **public repository** เพื่อใช้ standard GitHub-hosted runner โดยไม่มีค่า compute ตามเงื่อนไขปัจจุบัน อย่าเผยแพร่ webhook หรือไฟล์ .env
2. สร้าง Webhook ในห้อง Discord ที่ต้องการรับแจ้งเตือน: Server Settings → Integrations → Webhooks → New Webhook → เลือกห้อง → Copy Webhook URL (ต้องมีสิทธิ์จัดการ webhook)
3. GitHub repo → Settings → Secrets and variables → Actions → Secrets → New repository secret:
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: วาง Webhook URL โดยตรงที่ GitHub **ไม่ต้องส่งในแชต**
4. Actions → **Check train seats** → Run workflow บน default branch → mode `dry-run` ดูว่า `errors: []` และมีรายการตู้นอนทั้งสองวัน นี่เป็นการทดสอบการเข้าถึงจาก GitHub runner จริง
5. Run workflow → mode `initialize` **ครั้งเดียว** เพื่อสร้าง branch `monitor-state` และ `state.json` ห้ามลบ/รีเซ็ต state ระหว่างเฝ้าตรวจ เพราะอาจแจ้งซ้ำ
6. Run workflow → mode `test-discord` ตรวจว่าข้อความทดสอบถึงห้อง Discord จริง โหมดนี้ไม่อ้างว่าพบที่ว่าง
7. Run workflow → mode `check` ต้องสำเร็จ; หากทุกตู้เต็ม จะไม่มีข้อความแจ้งที่นั่ง
8. Settings → Secrets and variables → Actions → **Variables** → New repository variable: `MONITOR_ENABLED` = `true` เพื่อเริ่ม schedule แล้วตรวจว่ามี scheduled run เกิดขึ้นและสำเร็จจริง

หยุดชั่วคราว: เปลี่ยน `MONITOR_ENABLED` เป็น `false` หรือ Disable workflow. การกด Run workflow แบบ manual ยังทำงานได้แม้ variable เป็น false

`GITHUB_TOKEN` มีให้อัตโนมัติใน Actions และต้องเขียน contents ได้ workflow ขอสิทธิ์เฉพาะ job ที่ต้องบันทึก state หากองค์กรบล็อกสิทธิ์นี้ ต้องให้เจ้าของ repo จัดการก่อน

## ใช้ในเครื่อง

Python 3.11+ ไม่ต้องติดตั้งแพ็กเกจเพิ่ม:

```powershell
python -m unittest discover -s tests -v
python -m train_alert --mode dry-run
python -m train_alert --mode initialize
```

ตั้ง environment variable `DISCORD_WEBHOOK_URL` ในเครื่องผ่านช่องทางส่วนตัว แล้วรัน:

```powershell
python -m train_alert --mode test-discord
python -m train_alert --mode check
```

แต่ละคำสั่งทำงาน **หนึ่งรอบ** และออก ไม่ใช่ daemon หากต้องการใช้ในเครื่องต่อเนื่องให้ตั้ง Windows Task Scheduler ทุก 5 นาทีและเลือก **Do not start a new instance** เมื่อรอบก่อนยังไม่จบ อย่ารัน local monitor ซ้อนกันหรือใช้ state คนละชุดสำหรับห้องเดียวกัน

## ข้อจำกัดและการดูแล

- state อยู่ใน branch `monitor-state` ใช้ GitHub Contents API พร้อม SHA ป้องกันเขียนทับข้อมูลที่เปลี่ยนไป และ workflow concurrency ป้องกันรันซ้อน
- heartbeat commit แต่ละรอบสร้าง repository activity แต่ยังควรดูหน้า Actions ว่ามี run สำเร็จล่าสุด โดยเฉพาะเมื่อเข้าใกล้วันเดินทาง GitHub อาจปิด scheduled workflow ของ public repo ที่ไม่มี activity 60 วัน ตัวโปรแกรมเองแจ้งไม่ได้หาก workflow ไม่ได้เริ่มรันเลย
- ถ้า Discord ใช้งานไม่ได้ จะเก็บ pending และ workflow แสดง failed หากส่งสำเร็จแต่บันทึกยืนยันไม่สำเร็จ/การตอบรับขาดหาย อาจมีข้อความซ้ำ เป็นข้อจำกัดของการส่งข้ามสองบริการ
- ไม่ใช้ cache เป็นที่เก็บ state หลัก เพราะ cache อาจหายได้
- ถ้า config เปลี่ยน ระบบจะหยุดเมื่อ fingerprint ไม่ตรง ต้องวางแผนย้าย state ก่อนเปลี่ยนเส้นทาง/วัน ไม่รีเซ็ตอัตโนมัติ
- API นี้เป็น endpoint ภายในหน้าเว็บ ไม่ใช่ public API ที่รับประกันความเข้ากันได้ ทดสอบสำเร็จวันที่ 9 ต.ค. 2026 หากรูปแบบเปลี่ยนจะหยุดแจ้ง availability และแสดง error
- ต้องทดสอบบน GitHub runner จริงก่อนอ้างว่าเฝ้าตรวจแล้ว การผ่านจากเครื่อง Windows ไม่รับประกันการเข้าถึงจาก GitHub

## แหล่งอ้างอิง

- [D-Ticket](https://dticket.railway.co.th/DTicketPublicWeb/home/Home)
- [การตั้งเวลาและข้อจำกัด GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [ค่าใช้จ่าย GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Discord webhooks](https://docs.discord.com/developers/resources/webhook)

ผลตรวจเริ่มต้นอยู่ใน `dticket-check-2026-10-09.json` เป็นหลักฐานในอดีต ไม่ใช่สถานะปัจจุบัน

## สถานะการติดตั้งครั้งแรก

วันที่ 9 ต.ค. 2026: ชุดทดสอบ 32 กรณีผ่านทั้งในเครื่องและ GitHub; [dry-run บน GitHub runner](https://github.com/KrisBunuabenjamas/thai-train-seat-alert/actions/runs/37946452570) อ่าน 10 กลุ่มตู้นอนสำเร็จโดยไม่มี error และ initialize state สำเร็จแล้ว

**ยังไม่ได้เปิด schedule:** รอเจ้าของ repo เพิ่ม `DISCORD_WEBHOOK_URL` แล้วทดสอบ Discord/check ก่อนตั้ง `MONITOR_ENABLED=true` ไม่ต้อง initialize ซ้ำ
