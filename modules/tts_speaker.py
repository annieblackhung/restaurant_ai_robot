"""
Vietnamese Text-to-Speech speaker for Restaurant AI Robot.

Không dùng playsound vì trên Ubuntu playsound thường lỗi:
    TTS error: No module named 'gi'

Cách cài:
    pip uninstall -y playsound
    pip install gTTS pygame

Cách dùng:
    from modules.tts_speaker import RobotSpeaker

    self.speaker = RobotSpeaker(lang="vi")
    self.speaker.speak("Xin chào quý khách.")
"""

from __future__ import annotations

import os
import tempfile
import threading
import time


class RobotSpeaker:
    def __init__(self, lang: str = "vi", enabled: bool = True):
        self.lang = lang
        self.enabled = enabled
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        """
        Đọc text bằng tiếng Việt.
        Chạy trong thread riêng để không làm treo GUI.
        """
        text = (text or "").strip()
        if not self.enabled or not text:
            return

        threading.Thread(
            target=self._speak_worker,
            args=(text,),
            daemon=True
        ).start()

    def _speak_worker(self, text: str) -> None:
        """
        Tạo file mp3 bằng gTTS, phát bằng pygame.
        Dùng lock để tránh nhiều câu nói chồng lên nhau.
        """
        with self._lock:
            temp_path = None

            try:
                from gtts import gTTS
                import pygame

                with tempfile.NamedTemporaryFile(
                    suffix=".mp3",
                    delete=False
                ) as temp_file:
                    temp_path = temp_file.name

                tts = gTTS(text=text, lang=self.lang)
                tts.save(temp_path)

                if not pygame.mixer.get_init():
                    pygame.mixer.init()

                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)

                pygame.mixer.music.unload()

            except Exception as exc:
                print("TTS error:", exc)

            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled
