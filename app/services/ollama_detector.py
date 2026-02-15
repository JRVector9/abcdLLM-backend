"""
Ollama 자동 감지 모듈
백엔드 시작 시 Ollama 서버를 자동으로 찾아 설정합니다.
"""
import asyncio
import socket
import httpx


async def detect_ollama_url() -> str | None:
    """
    여러 가능한 Ollama URL을 테스트하여 작동하는 URL을 반환합니다.

    테스트 순서:
    1. http://localhost:11434 (로컬 직접 실행)
    2. http://127.0.0.1:11434 (로컬 직접 실행)
    3. http://host.docker.internal:11434 (Docker Desktop)
    4. http://host.orb.internal:11434 (OrbStack)
    5. http://[gateway_ip]:11434 (Docker 네트워크 게이트웨이)
    6. http://[host_ip]:11434 (호스트 머신 IP - Mac/Linux)
    """

    # 후보 URL 목록
    candidates = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://host.docker.internal:11434",  # Docker Desktop
        "http://host.orb.internal:11434",     # OrbStack
    ]

    # Docker 게이트웨이 IP 추가
    gateway_ip = _get_docker_gateway_ip()
    if gateway_ip:
        candidates.append(f"http://{gateway_ip}:11434")

    # 호스트 머신 IP 추가 (Mac/Linux)
    host_ips = _get_host_ips()
    for ip in host_ips:
        if ip not in ["127.0.0.1", "localhost"]:
            candidates.append(f"http://{ip}:11434")

    print(f"🔍 Ollama 자동 감지 시작... ({len(candidates)}개 후보)")

    # 각 URL을 순차적으로 테스트
    for url in candidates:
        if await _test_ollama_url(url):
            print(f"✅ Ollama 발견: {url}")
            return url
        else:
            print(f"   ❌ {url} - 응답 없음")

    print("⚠️ Ollama를 찾을 수 없습니다. 기본값 사용")
    return None


async def _test_ollama_url(url: str, timeout: float = 2.0) -> bool:
    """URL이 Ollama 서버인지 테스트"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


def _get_docker_gateway_ip() -> str | None:
    """Docker 네트워크 게이트웨이 IP 가져오기"""
    try:
        # /proc/net/route 파일에서 게이트웨이 IP 찾기 (Linux)
        with open("/proc/net/route", "r") as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == "00000000":  # Default route
                    # Gateway IP를 hex에서 decimal로 변환
                    gateway_hex = fields[2]
                    gateway_parts = [
                        str(int(gateway_hex[i:i+2], 16))
                        for i in range(0, 8, 2)
                    ]
                    return ".".join(reversed(gateway_parts))
    except Exception:
        pass

    # ip route 명령 사용 (대안)
    try:
        import subprocess
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            # "default via 172.17.0.1 dev eth0" 형식 파싱
            parts = result.stdout.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                return parts[2]
    except Exception:
        pass

    return None


def _get_host_ips() -> list[str]:
    """호스트 머신의 IP 주소 목록 가져오기"""
    ips = []

    try:
        # 호스트네임으로 IP 가져오기
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip:
            ips.append(ip)
    except Exception:
        pass

    # 모든 네트워크 인터페이스의 IP 가져오기
    try:
        import subprocess
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            # "192.168.1.100 172.17.0.1" 형식
            for ip in result.stdout.strip().split():
                if ip and ip not in ips:
                    ips.append(ip)
    except Exception:
        pass

    return ips


async def auto_configure_ollama() -> None:
    """
    Ollama를 자동으로 감지하고 DB에 저장합니다.
    백엔드 startup 이벤트에서 호출합니다.
    """
    from app.database import pb

    print("\n" + "="*60)
    print("Ollama 자동 구성 시작")
    print("="*60)

    # DB에 이미 설정이 있는지 확인
    try:
        results = pb.collection("system_settings").get_list(
            1, 1, {"filter": 'key="ollama_base_url"'}
        )
        if results.items:
            current_url = getattr(results.items[0], "value", "")
            print(f"💾 기존 설정 발견: {current_url}")

            # 기존 설정이 작동하는지 테스트
            if await _test_ollama_url(current_url):
                print(f"✅ 기존 설정 작동 중: {current_url}")
                print("="*60 + "\n")
                return
            else:
                print(f"⚠️ 기존 설정 응답 없음: {current_url}")
                print("   새로운 Ollama 서버를 찾습니다...")
    except Exception as e:
        print(f"⚠️ DB 조회 실패: {e}")

    # 자동 감지 실행
    detected_url = await detect_ollama_url()

    if detected_url:
        # DB에 저장
        try:
            # 기존 설정 업데이트 또는 새로 생성
            results = pb.collection("system_settings").get_list(
                1, 1, {"filter": 'key="ollama_base_url"'}
            )

            if results.items:
                # 업데이트
                pb.collection("system_settings").update(results.items[0].id, {
                    "value": detected_url,
                    "description": "자동 감지된 Ollama URL",
                })
                print(f"💾 DB 업데이트 완료: {detected_url}")
            else:
                # 새로 생성
                pb.collection("system_settings").create({
                    "key": "ollama_base_url",
                    "value": detected_url,
                    "description": "자동 감지된 Ollama URL",
                })
                print(f"💾 DB 저장 완료: {detected_url}")

            # 클라이언트 재설정
            from app.services import ollama_client
            ollama_client.reset_client()
            print("🔄 Ollama 클라이언트 재설정 완료")

        except Exception as e:
            print(f"❌ DB 저장 실패: {e}")
    else:
        print("⚠️ Ollama를 찾을 수 없습니다.")
        print("   기본 URL(http://127.0.0.1:11434) 사용")

    print("="*60 + "\n")
