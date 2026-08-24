<p align="center">
  <img src="assets/readme-cover.png" alt="Mini Program Engineering Skill Suite cover" width="100%">
</p>

# Mini Program Engineering Skill Suite

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/platform-WeChat%20Mini%20Program-07C160.svg" alt="Platform: WeChat Mini Program">
  <img src="https://img.shields.io/badge/type-Agent%20Skill%20Suite-7B61FF.svg" alt="Type: Agent Skill Suite">
  <img src="https://img.shields.io/badge/category-Evidence--First%20Engineering-FF6B35.svg" alt="Category: Evidence-First Engineering">
  <img src="https://img.shields.io/badge/stack-Taro%20%7C%20uni--app%20%7C%20native-4CAF50.svg" alt="Stack: Taro / uni-app / native">
  <img src="https://img.shields.io/badge/runtime-Python%203.9%2B-3776AB.svg" alt="Runtime: Python 3.9+">
  <img src="https://img.shields.io/badge/lang-ไทย-F97316.svg" alt="Language: ไทย">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-1.1.0-0EA5E9.svg" alt="Version: 1.1.0">
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README.zh-Hant.md">繁體中文</a> ·
  <a href="./README.en.md">English</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.th.md">ไทย</a> ·
  <a href="./README.id.md">Bahasa Indonesia</a>
</p>

**Mini Program Engineering Skill Suite** คือชุด Agent Skill สำหรับช่วยพัฒนา WeChat Mini Program ตั้งแต่เริ่มต้น รับช่วงต่อโปรเจกต์เดิม และเตรียมความพร้อมก่อนปล่อยใช้งานจริง โดยแยกงานออกเป็นขั้นตอนที่ตรวจสอบได้: ต้องทำอะไร ทำอย่างไร ทำถึงขั้นไหน และมีหลักฐานอะไรยืนยัน

ชื่อภาษาจีน: **小程序开发工程技能套件**.

> หมายเหตุ: ชุดนี้โฟกัสที่กระบวนการวิศวกรรมของ WeChat Mini Program เป็นหลัก หากต้องการใช้กับ LINE MINI App, Telegram Mini Apps หรือ Alipay+ Mini Program สามารถนำแนวคิดไปปรับใช้ได้ แต่ต้องตรวจสอบกฎ แพลตฟอร์ม สิทธิ์ การชำระเงิน และ runtime ของแต่ละระบบแยกต่างหาก

---

## เข้าใจ Skill นี้ใน 30 วินาที

ถ้าต้องการดูภาพรวมว่าสิ่งนี้แก้ปัญหาอะไร มาจากโปรเจกต์จริงแบบไหน และควรใช้อย่างไร ให้เริ่มจาก[วิดีโออธิบาย 32 วินาที](https://raw.githubusercontent.com/NocodeMrLi/mini-program-engineering-skill-suite/main/assets/readme-promo.mp4)นี้

https://github.com/user-attachments/assets/73f542b6-f90d-4f1b-bb75-bb19db341dc5

<sub>วิดีโอนี้ใช้เพื่ออธิบายตำแหน่งของชุด Skill ที่มา และขอบเขตการใช้งานเท่านั้น</sub>

---

## สถานะโปรเจกต์

repository นี้เป็นหน้าโครงการสาธารณะของชุด Skill และเผยแพร่ภายใต้ **MIT License** คุณสามารถดู ใช้ แก้ไข และแจกจ่ายต่อได้ ดูรายละเอียดได้ที่ [LICENSE](LICENSE)

---

## แก้ปัญหาอะไร

สำหรับคนที่ไม่เคยทำ mini program มาก่อน ความยากไม่ได้อยู่แค่การเขียนโค้ด แต่คือการรู้ว่าควรยืนยันอะไรก่อน ตัดสินใจอะไรจะกระทบขั้นตอนถัดไป ควรหยุดเพื่อตรวจสอบเมื่อไร และก่อนปล่อยจริงมีอะไรที่ห้ามข้ามด้วยความรู้สึก

ปัญหาที่พบบ่อย:

- ติดตั้ง environment แล้ว error หรือ config ไม่ตรงกัน；
- หลังปล่อยจึงพบว่าสิทธิ์หรือ privacy policy ยังไม่ครบ；
- UI เพี้ยนบนอุปกรณ์จริง แม้ดูดีใน simulator；
- สับสนระหว่าง build, submission, acceptance และ release；
- เผลอ push หรือปล่อยสิ่งที่ยังไม่ได้ยืนยัน ต้อง rollback ด่วน

ชุดนี้ช่วยให้ Agent เริ่มจากการเข้าใจเป้าหมายและขอบเขต สร้าง specification และแผนวิศวกรรม จากนั้นทำทีละขั้น ตรวจสอบเป็นชั้น ๆ และจัดการความเสี่ยงก่อน release มันไม่แทนที่การตัดสินใจทางธุรกิจหรือผลิตภัณฑ์ แต่ช่วยให้ผู้ใช้รู้ว่า “ขั้นต่อไปคืออะไร ทำไปทำไม และต้องมีหลักฐานแค่ไหน”

---

## ที่มาจากโปรเจกต์จริง: WordPet

Skill นี้ไม่ได้เขียนจาก tutorial เชิงนามธรรม แต่สกัดมาจากการทำงานระยะยาวบน WeChat Mini Program จริงชื่อ **WordPet** สิ่งที่เผยแพร่ใน repository นี้คือวิธีการที่นำกลับมาใช้ซ้ำได้: การแยกงานผลิตภัณฑ์ การลงมือทำ การตรวจสอบ การยอมรับงาน ความพร้อมก่อน release และการจัดการหลักฐาน

<p align="center">
  <img src="assets/wordpet-origin-case.png" alt="WordPet real project origin case" width="100%">
</p>

<sub>WordPet แสดงเป็นกรณีต้นทางเท่านั้น repository นี้ไม่รวม source code, AppID, cloud resources, private configuration, business data, review status หรือ internal development records ของ mini program ดังกล่าว</sub>

---

## ช่วยให้ Agent ทำอะไรได้

- **รับช่วงต่อโปรเจกต์**: อ่านสถานะปัจจุบันก่อนแก้ไข เพื่อไม่ทำลายงานที่เสร็จแล้ว；
- **ทำ requirement ให้ชัด**: เปลี่ยนไอเดียกว้าง ๆ เป็น specification ที่ตรวจรับได้；
- **บันทึก decision**: เชื่อมการตัดสินใจเข้ากับ architecture, data, API, permission และ fallback；
- **แก้โค้ดอย่างปลอดภัย**: ทำทีละส่วนเล็ก ๆ และ rollback ได้；
- **ตรวจสอบเป็นชั้น**: แยก UI preview, user confirmation, integration, device check และ final acceptance；
- **debug ด้วยหลักฐาน**: ใช้ evidence แทนการเดา；
- **รายงานตรงไปตรงมา**: บอกเฉพาะสิ่งที่ตรวจสอบแล้ว

---

## ความสามารถหลัก

| ส่วน | หน้าที่ |
| --- | --- |
| Project intake | อ่านโปรเจกต์แบบ read-only เพื่อทำ fact map, risk map และ change boundary |
| Product specification | MVP scope, user flow, state matrix และ acceptance criteria |
| Architecture | module, data, API, permission และ failure strategy |
| Platform adaptation | เครื่องมือ WeChat Mini Program, privacy, permission และ platform evidence |
| Implementation | scoped changes, tests และการปกป้องงานเดิม |
| UI and device adaptation | preview-first, responsive และตรวจหลายอุปกรณ์ |
| Debugging | reproduction, competing hypotheses, root cause และ regression coverage |
| Verification | static, unit, integration, simulator, device, cloud และ release evidence |
| Release readiness | version, build, security, privacy, rollback, upload / review / release governance |

---

## วิธีใช้

clone repository นี้ไปยัง directory ของ Agent app ที่รองรับ `SKILL.md` หรือ project rules ถ้าไม่อยากติดตั้งเอง ให้ส่งข้อความนี้ให้ Agent ที่คุณใช้อยู่:

```text
https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git ช่วยติดตั้ง skill นี้ให้ฉัน
```

ตัวอย่าง:

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.agents/skills/mini-program-engineering-suite
```

หลังติดตั้ง ให้เปิด session ใหม่แล้วเรียกใช้:

```text
/mini-program-engineering-suite ฉันอยากทำ WeChat Mini Program จาก 0 ถึง 1 ช่วยเริ่มจาก product scope และ development steps
```

---

## สิ่งที่ไม่ทำ

ชุดนี้ไม่ติดตั้ง dependencies อัตโนมัติ ไม่สร้าง cloud resources ไม่ upload package ไม่ submit review ไม่ publish release และไม่เปลี่ยน online state เอง ทุก external write action ต้องได้รับอนุญาตแยกต่างหาก

---

## การตรวจสอบและความสมบูรณ์ของ package

ก่อนถือว่า release พร้อมใช้งาน จะมี structural validation, sensitive-content scan, deterministic public-package export, manifest verification, routing evaluation, behavior evaluation และ independent final review

```bash
python3 <package-dir>/scripts/verify_public_package.py <package-dir>
```

เวอร์ชันปัจจุบัน: **1.1.0**. License: **MIT License**.
