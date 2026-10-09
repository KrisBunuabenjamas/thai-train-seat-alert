import re
from urllib.parse import urlsplit
from .http import HTTP, HttpError


def payload(event):
    kind = event['kind']
    if kind == 'availability':
        o = event['observation']
        content = (f'🚨 พบที่นอนกลับมาว่าง!\nกรุงเทพอภิวัฒน์ → อุดรธานี\n'
                   f'วันเดินทาง {o["date"]} | ขบวน {o["train"]}\n'
                   f'ออก {o["departure_at"][11:16]} น. | ถึง {o["arrival_time"]} น.\n'
                   f'{o["description"]}\nว่าง {o["count"]} ที่\n'
                   f'ตรวจเมื่อ {event["checked_at"]}\n'
                   'เปิดจอง: https://dticket.railway.co.th/DTicketPublicWeb/home/Home\n'
                   'ที่นั่งอาจถูกจองก่อนเปิดเว็บ กรุณาตรวจเงื่อนไขผู้โดยสารของตู้')
    elif kind == 'health_failure':
        content = ('⚠️ ตัวเฝ้าตรวจ D-Ticket มีข้อผิดพลาดต่อเนื่องอย่างน้อย 3 รอบ\n'
                   'ยังยืนยันที่นั่งไม่ได้ โปรดดู GitHub Actions; ระบบจะลองใหม่รอบถัดไป')
    elif kind == 'health_recovery':
        content = '✅ ตัวเฝ้าตรวจ D-Ticket กลับมาตรวจได้ตามปกติแล้ว'
    elif kind == 'test':
        content = ('🔔 ทดสอบการแจ้งเตือนรถไฟสำเร็จ\nกรุงเทพอภิวัฒน์ → อุดรธานี 29–30 ธ.ค. 2026\n'
                   'นี่คือข้อความทดสอบ ไม่ใช่การพบที่นั่งว่าง')
    else:
        raise ValueError('Unknown notification type')
    return {'content': content[:2000], 'allowed_mentions': {'parse': []}}


class Discord:
    def __init__(self, webhook, http=None):
        parts = urlsplit(webhook)
        if (parts.scheme != 'https' or parts.netloc not in ('discord.com', 'discordapp.com')
                or not re.fullmatch(r'/api/webhooks/\d+/[A-Za-z0-9_.-]+', parts.path)
                or parts.query or parts.fragment):
            raise ValueError('Set DISCORD_WEBHOOK_URL to a valid Discord channel webhook')
        # Defer retries to the next poll, which revalidates both seats and departure.
        self.webhook, self.http = webhook, http or HTTP(attempts=1)

    def send(self, event):
        try:
            # wait=true asks Discord to acknowledge that the message was created.
            self.http.request('POST', self.webhook + '?wait=true', json_body=payload(event))
        except HttpError:
            raise RuntimeError('Discord delivery failed; queued for a later check') from None
