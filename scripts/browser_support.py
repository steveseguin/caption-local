"""Browser selection for Windows/Linux tests, without changing installed browsers."""
import os
from pathlib import Path


def browser_options():
    explicit = os.environ.get('CAPTION_TEST_BROWSER')
    if explicit:
        if not Path(explicit).is_file():
            raise RuntimeError(f'CAPTION_TEST_BROWSER does not exist: {explicit}')
        return {'executable_path': explicit}
    if os.name == 'nt':
        for variable in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
            base = Path(os.environ.get(variable, ''))
            for relative in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
                candidate = base / relative
                if candidate.is_file():
                    return {'executable_path': str(candidate)}
    elif Path('/usr/bin/google-chrome').is_file():
        return {'executable_path': '/usr/bin/google-chrome'}
    # Install with: python -m playwright install chromium
    return {}


def authenticate(page):
    """Supply a configured local token in tab memory, never as global HTTP headers."""
    if page.locator('#connection').count():
        page.fill('#connectionToken', os.environ.get('CAPTION_API_KEY', ''))
        page.click('#connect')
    elif os.environ.get('CAPTION_API_KEY'):
        page.evaluate('token => { serviceToken=token; return health(); }', os.environ['CAPTION_API_KEY'])


async def authenticate_async(page):
    if await page.locator('#connection').count():
        await page.fill('#connectionToken', os.environ.get('CAPTION_API_KEY', ''))
        await page.click('#connect')
    elif os.environ.get('CAPTION_API_KEY'):
        await page.evaluate('token => { serviceToken=token; return health(); }', os.environ['CAPTION_API_KEY'])
