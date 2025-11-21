import json
import os
import sys
import signal
import time
import threading
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

# --- Cấu hình hằng số ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / 'logs'
LOG_FILE = LOG_DIR / 'latest.log'
CONFIG_FILE = BASE_DIR / 'multiprocess.json'
REQUIREMENTS_FILE = BASE_DIR / 'requirements.txt'

MIN_PYTHON_VERSION = (3, 10)
MAX_PYTHON_VERSION = (3, 13)

def rgb_gradient_text(text: str, start_rgb: Tuple[int, int, int] = (255, 0, 0), end_rgb: Tuple[int, int, int] = (0, 0, 255)) -> str:
    """Tạo gradient RGB thật mượt cho chuỗi text."""
    result = ""
    r1, g1, b1 = start_rgb
    r2, g2, b2 = end_rgb
    
    char_count = len(text)
    divisor = max(char_count - 1, 1)

    for i, ch in enumerate(text):
        ratio = i / divisor
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        result += f"\033[38;2;{r};{g};{b}m{ch}\033[0m"
    return result

def print_banner():
    """In banner ASCII art với hiệu ứng màu sắc."""
    banner = r"""
▐▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▌
▐  ███╗   ███╗ █████╗ ██╗  ██╗███████╗    ██████╗ ██╗   ██╗                   ▌
▐  ████╗ ████║██╔══██╗██║ ██╔╝██╔════╝    ██╔══██╗╚██╗ ██╔╝                   ▌
▐  ██╔████╔██║███████║█████╔╝ █████╗      ██████╔╝ ╚████╔╝                    ▌
▐  ██║╚██╔╝██║██╔══██║██╔═██╗ ██╔══╝      ██╔══██╗  ╚██╔╝                     ▌
▐  ██║ ╚═╝ ██║██║  ██║██║  ██╗███████╗    ██████╔╝   ██║                      ▌
▐  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝    ╚═════╝    ╚═╝                      ▌
▐                                                                             ▌
▐  ██╗  ██╗██╗███████╗███╗   ██╗██████╗  ██████╗ ██╗██████╗ ██████╗ ██╗  ██╗  ▌
▐  ██║ ██╔╝██║██╔════╝████╗  ██║██╔══██╗██╔════╝███║╚════██╗╚════██╗██║  ██║  ▌
▐  █████╔╝ ██║█████╗  ██╔██╗ ██║██████╔╝██║     ╚██║ █████╔╝ █████╔╝███████║  ▌
▐  ██╔═██╗ ██║██╔══╝  ██║╚██╗██║██╔═══╝ ██║      ██║██╔═══╝  ╚═══██╗╚════██║  ▌
▐  ██║  ██╗██║███████╗██║ ╚████║██║     ╚██████╗ ██║███████╗██████╔╝     ██║  ▌
▐  ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═══╝╚═╝      ╚═════╝ ╚═╝╚══════╝╚═════╝      ╚═╝  ▌
▐▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▌
Credit: https://github.com/KienPC1234
"""
    lines = banner.splitlines()
    colors = [
        (255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
        (0, 255, 255), (0, 127, 255), (127, 0, 255), (255, 0, 255),
    ]
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        print(rgb_gradient_text(line, start_rgb=color, end_rgb=colors[(i + 1) % len(colors)]))
        time.sleep(0.01)
    print("\n")

def check_python_version():
    """Kiểm tra phiên bản Python có nằm trong khoảng yêu cầu không."""
    current_version = sys.version_info
    if not (MIN_PYTHON_VERSION <= current_version < MAX_PYTHON_VERSION):
        print(f"Lỗi: Phiên bản Python không tương thích.")
        print(f"Yêu cầu Python >= {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} và < {MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}")
        print(f"Bạn đang dùng {current_version.major}.{current_version.minor}.")
        sys.exit(1)
    print(f"Phiên bản Python {current_version.major}.{current_version.minor} hợp lệ.")


class ProcessManager:
    """
    Quản lý (khởi chạy, giám sát, khởi động lại, và tắt) các tiến trình con.
    """
    def __init__(self, config_file: Path):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"Lỗi: File config '{config_file}' không tồn tại.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Lỗi: File config '{config_file}' không hợp lệ: {e}")
            sys.exit(1)
        
        self.processes: Dict[str, Dict[str, Any]] = {}
        self.log_lock = threading.Lock()
        self.log_file_handle: Optional[Any] = None

    def start_process(self, name: str, cmd: List[str]):
        """
        Khởi động một tiến trình con, bắt output và tạo luồng log.
        Thêm `creationflags` cho Windows để việc tắt tiến trình đáng tin cậy hơn.
        """
        print(f"Khởi động tiến trình [{name}]: {' '.join(cmd)}")
        
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=BASE_DIR, 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                preexec_fn=os.setsid if sys.platform != "win32" else None,
                creationflags=creationflags
            )
            self.processes[name] = {'proc': proc, 'cmd': cmd}
            self._start_log_thread(name, proc)
        except Exception as e:
            print(f"Lỗi khi khởi động [{name}]: {e}")

    def _start_log_thread(self, name: str, proc: subprocess.Popen):
        """
        Tạo một luồng riêng để đọc output từ tiến trình con.
        Sử dụng một file handle duy nhất và một Lock để đảm bảo thread-safe khi ghi log.
        """
        def log_reader():
            if not self.log_file_handle:
                return
                
            for line in iter(proc.stdout.readline, ''):
                if line.strip():
                    prefixed_line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{name}] {line.strip()}\n"
                    
                    print(prefixed_line.strip())
                    
                    try:
                        with self.log_lock:
                            self.log_file_handle.write(prefixed_line)
                            self.log_file_handle.flush()
                    except Exception as e:
                        if "closed file" in str(e):
                            break
                        print(f"Lỗi ghi log từ [{name}]: {e}")
            
            proc.stdout.close()

        t = threading.Thread(target=log_reader, daemon=True)
        t.start()
        self.processes[name]['log_thread'] = t

    def monitor_and_restart(self):
        """Vòng lặp vô hạn giám sát và khởi động lại tiến trình nếu bị lỗi."""
        while True:
            try:
                for name in list(self.processes.keys()):
                    info = self.processes[name]
                    if info['proc'].poll() is not None:
                        print(f"Tiến trình [{name}] đã dừng (mã lỗi: {info['proc'].returncode}). Đang khởi động lại...")
                        self.start_process(name, info['cmd'])
                time.sleep(5)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Lỗi trong vòng lặp giám sát: {e}")
                time.sleep(10)

    def shutdown(self, signum=None, frame=None):
        """
        Tắt tất cả tiến trình con một cách an toàn.
        Tắt theo thứ tự ngược lại, sử dụng terminate() trước, chờ (wait), rồi mới kill() (bắt buộc).
        """
        print("\nĐang tắt ứng dụng... Gửi tín hiệu dừng đến các tiến trình con.")
        
        for name, info in reversed(self.processes.items()):
            proc = info['proc']
            if proc.poll() is None:
                print(f" - Đang dừng [{name}] (PID: {proc.pid})...", end='', flush=True)
                try:
                    if sys.platform != "win32":
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    else:
                        proc.terminate()
                    
                    proc.wait(timeout=5)
                    print(" [OK]")

                except subprocess.TimeoutExpired:
                    print(" [Timeout! Buộc dừng]... ", end='', flush=True)
                    if sys.platform != "win32":
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                    print("[KILLED]")
                except Exception as e:
                    print(f" [Lỗi: {e}]")
                    try:
                        proc.kill()
                    except:
                        pass
            else:
                 print(f" - Tiến trình [{name}] đã dừng từ trước.")

        if self.log_file_handle:
            print("Đóng file log...")
            self.log_file_handle.close()
            
        print("Đã tắt xong. Tạm biệt!")
        sys.exit(0)

    def run(self):
        """Khởi chạy toàn bộ quy trình."""
        print_banner()
        check_python_version()
        
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        try:
            self.log_file_handle = LOG_FILE.open('a', encoding='utf-8')
        except IOError as e:
            print(f"Lỗi: Không thể mở file log {LOG_FILE}: {e}")
            sys.exit(1)
            
        print("--- Khởi động các tiến trình con ---")
        for name, cmd in self.config.items():
            self.start_process(name, cmd)
        
        print("\n" + "="*40)
        print("Tất cả tiến trình đã được khởi động.")
        print(f"Log đang được ghi tại: {LOG_FILE}")
        print("Nhấn Ctrl+C để tắt ứng dụng một cách an toàn.")
        print("="*40 + "\n")
        
        self.monitor_and_restart()

def main():
    """Hàm chính của script."""
    os.chdir(BASE_DIR)
    
    LOG_DIR.mkdir(exist_ok=True)
    
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
    except OSError as e:
        print(f"Cảnh báo: Không thể xóa file log cũ {LOG_FILE}: {e}")

    try:
        pm = ProcessManager(config_file=CONFIG_FILE)
        pm.run()
    except Exception as e:
        print(f"Lỗi nghiêm trọng không xác định: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()