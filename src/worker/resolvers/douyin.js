const { chromium } = require('playwright')
const fs = require('fs')
const os = require('os')
const path = require('path')

const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

function findChromium() {
  const cache = path.join(os.homedir(), '.cache', 'ms-playwright')
  if (!fs.existsSync(cache)) {
    return undefined
  }
  const entries = fs
    .readdirSync(cache)
    .filter((name) => name.startsWith('chromium-'))
    .sort()
    .reverse()
  for (const entry of entries) {
    for (const sub of ['chrome-linux64/chrome', 'chrome-linux/chrome']) {
      const candidate = path.join(cache, entry, sub)
      if (fs.existsSync(candidate)) {
        return candidate
      }
    }
  }
  return undefined
}

async function main() {
  const [url, output] = process.argv.slice(2)
  if (!url || !output) {
    throw new Error('usage: node douyin.js <url> <output>')
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath: findChromium(),
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  })

  try {
    const context = await browser.newContext({
      userAgent: UA,
      viewport: { width: 1280, height: 800 },
      locale: 'zh-CN',
    })
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined })
    })

    const page = await context.newPage()
    let detail = null
    page.on('response', async (response) => {
      if (response.url().includes('/aweme/v1/web/aweme/detail')) {
        try {
          detail = await response.json()
        } catch (error) {
          // ignore non-JSON responses
        }
      }
    })

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
    const deadline = Date.now() + 30000
    while (!detail && Date.now() < deadline) {
      await page.waitForTimeout(1000)
    }

    if (!detail || !detail.aweme_detail) {
      throw new Error('无法获取抖音视频信息（页面可能需要验证）')
    }

    const item = detail.aweme_detail
    const candidates = []
    for (const rate of (item.video && item.video.bit_rate) || []) {
      for (const link of (rate.play_addr && rate.play_addr.url_list) || []) {
        candidates.push(link)
      }
    }
    for (const link of (item.video && item.video.play_addr && item.video.play_addr.url_list) || []) {
      candidates.push(link)
    }

    let size = 0
    for (const videoUrl of candidates.slice(0, 8)) {
      try {
        const response = await context.request.get(videoUrl, {
          headers: { Referer: 'https://www.douyin.com/', 'User-Agent': UA },
          timeout: 120000,
        })
        if (!response.ok()) {
          continue
        }
        const body = await response.body()
        if (body.length < 10000) {
          continue
        }
        fs.writeFileSync(output, body)
        size = body.length
        break
      } catch (error) {
        // try the next candidate
      }
    }

    if (!size) {
      throw new Error('视频下载失败')
    }

    console.log(
      JSON.stringify({
        ok: true,
        title: item.desc || '',
        duration_ms: (item.video && item.video.duration) || 0,
        size,
      }),
    )
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  const message = error && error.message ? error.message : String(error)
  console.error(JSON.stringify({ ok: false, error: message }))
  process.exit(1)
})
