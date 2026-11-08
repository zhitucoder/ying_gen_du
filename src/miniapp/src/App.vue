<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

import { ensureLogin } from '@/api/auth'

onLaunch(() => {
  ensureLogin().catch(() => {})
})
</script>

<style>
page {
  background: #f5f6f8;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
}
</style>
