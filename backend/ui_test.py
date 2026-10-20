"""Playwright end-to-end UI test: home -> story -> storyboard -> narration -> rendered MP4."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
CHROME = "/opt/playwright/browsers/chromium-1243/chrome-linux64/chrome"
shots = "/home/user/storyforge-ai/data/screenshots"
import os
os.makedirs(shots, exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1. Home
        page.goto(BASE, wait_until="networkidle")
        assert "Turn Your Stories Into" in page.inner_text("body"), "headline missing"
        assert "Create a Story Video" in page.inner_text("body")
        page.screenshot(path=f"{shots}/01_home.png", full_page=True)
        print("1/7 home OK")

        # 2. New story project -> Studio
        page.click("text=Create a Story Video")
        page.wait_for_selector("text=Story setup")
        page.select_option("select >> nth=0", "horror")
        page.fill('input[type="number"]', "3")
        page.screenshot(path=f"{shots}/02_studio.png")
        page.click("text=Generate original script")
        page.wait_for_selector("text=Approve & build storyboard", timeout=60000)
        print("2/7 script generated")
        page.screenshot(path=f"{shots}/03_script_pack.png")
        page.click("text=Approve & build storyboard")

        # 3. Script editor
        page.wait_for_selector("text=Narration estimate")
        scenes = page.locator("text=Scene").count()
        assert scenes >= 3
        print("3/7 script editor OK, scene mentions:", scenes)

        # 4. Storyboard: placeholders + narration
        page.click("text=Storyboard")
        page.wait_for_selector("text=Local narration (Piper)")
        page.select_option("select >> nth=0", index=1)  # first voice
        page.click("text=All placeholders")
        page.wait_for_selector("text=Placeholder", timeout=60000)  # placeholder badge
        page.click("text=Narrate all scenes")
        page.wait_for_function("document.querySelectorAll('audio').length >= 3", timeout=180000)
        naudio = page.locator("audio").count()
        assert naudio >= 3
        page.screenshot(path=f"{shots}/04_storyboard.png", full_page=True)
        print("4/7 storyboard: placeholders +", naudio, "narration players")

        # 5. Timeline
        page.click("text=Timeline")
        page.wait_for_selector("text=Scene timeline")
        page.screenshot(path=f"{shots}/05_timeline.png")
        print("5/7 timeline OK")

        # 6. Export -> render
        page.click("text=Preview & Export")
        page.wait_for_selector("text=Render & export MP4")
        page.click("text=Render video with FFmpeg")
        page.wait_for_selector("text=Download MP4", timeout=300000)
        videos = page.locator("video").count()
        assert videos >= 1
        page.screenshot(path=f"{shots}/06_export.png", full_page=True)
        print("6/7 RENDER COMPLETE - video player present:", videos)

        # 7. Metadata + thumbnail + Clip mode honesty
        page.click("text=Generate titles, description & hashtags")
        page.wait_for_selector("text=Three title options")
        page.click("text=Generate thumbnail")
        page.wait_for_selector('img[alt="Thumbnail preview"]', timeout=30000)
        page.screenshot(path=f"{shots}/07_metadata_thumb.png", full_page=True)
        print("7/7 metadata + thumbnail OK")

        page.goto(BASE, wait_until="networkidle")
        page.click("text=Generate a Video Clip")
        page.wait_for_selector("text=Local model status")
        page.wait_for_selector("text=Not configured")
        page.wait_for_selector("text=No GPU detected")
        page.screenshot(path=f"{shots}/08_clip_mode.png", full_page=True)
        print("8/8 clip mode shows honest provider status")

        if errors:
            print("PAGE ERRORS:", errors)
        browser.close()
        print("\nUI TEST PASSED")


if __name__ == "__main__":
    sys.exit(main())
