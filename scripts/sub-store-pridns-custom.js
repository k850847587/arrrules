// 1. 改造后的按文件独立提取方法（不合并数据）
async function extractPsnAndDomainsByFile(psnFiles = "光速云-RAW.yaml") {
  let fileList = [];
  if (typeof psnFiles === 'string') {
    const trimmed = psnFiles.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try { fileList = JSON.parse(trimmed); } catch (e) { fileList = trimmed.split(',').map(s => s.trim()).filter(Boolean); }
    } else {
      fileList = trimmed.split(',').map(s => s.trim()).filter(Boolean);
    }
  } else if (Array.isArray(psnFiles)) {
    fileList = psnFiles;
  }

  const isIpv4 = (ip) => /^(\d{1,3}\.){3}\d{1,3}$/.test(ip);
  const isIpv6 = (ip) => /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/.test(ip) || ip.includes(':');

  async function loadRawYaml(fileName) {
    if (!fileName) return null;
    try {
      const rawResult = await produceArtifact({ type: 'file', name: fileName, produceType: 'raw' });
      const arr = typeof rawResult === 'string' ? JSON.parse(rawResult) : rawResult;
      const text = (Array.isArray(arr) ? arr : [arr]).filter(i => typeof i === 'string' && i.length > 0)[0];
      if (!text) return null;
      if (typeof ProxyUtils !== 'undefined' && ProxyUtils.yaml && typeof ProxyUtils.yaml.safeLoad === 'function') {
        return ProxyUtils.yaml.safeLoad(text);
      } else if (typeof $yaml !== 'undefined' && typeof $yaml.parse === 'function') {
        return $yaml.parse(text);
      }
    } catch (e) {
      $.error(`psnFile[${fileName}] 读取失败: ${e?.message || e}`);
    }
    return null;
  }

  const results = [];
  for (const fileName of fileList) {
    if (typeof fileName !== 'string' || !fileName) continue;
    const doc = await loadRawYaml(fileName);
    if (!doc) continue;

    const psnSet = new Set();
    const domainSet = new Set();

    // 提取该文件独有的 proxy-server-nameserver
    if (doc?.dns && doc.dns['proxy-server-nameserver']) {
      const dnsList = Array.isArray(doc.dns['proxy-server-nameserver']) ? doc.dns['proxy-server-nameserver'] : [doc.dns['proxy-server-nameserver']];
      dnsList.forEach(item => { if (item && typeof item === 'string') psnSet.add(item.trim()); });
    }

    // 提取该文件独有的 server 主域名
    if (Array.isArray(doc?.proxies)) {
      for (const proxy of doc.proxies) {
        const server = proxy?.server;
        if (!server || typeof server !== 'string' || isIpv4(server) || isIpv6(server)) continue;
        const parts = server.toLowerCase().trim().split('.').filter(Boolean);
        if (parts.length >= 2) {
          domainSet.add(parts.slice(-2).join('.'));
        }
      }
    }

    results.push({
      fileName,
      psnList: Array.from(psnSet),
      serverDomains: Array.from(domainSet)
    });
  }
  return results;
}
const $ = $substore;
// 2. 获取按文件分类的数据列表
const targetPsnFiles = $arguments?.psnFile || "光速云-RAW.yaml";
const fileResults = await extractPsnAndDomainsByFile(targetPsnFiles);

$.info("========== 开始处理 YAML ==========");

// 3. 解析全局变量 $content
const yaml = ProxyUtils.yaml.safeLoad($content);
yaml.dns = yaml.dns || {};

// 4. 处理 fake-ip-filter (汇总所有文件提取的域名)
const kzzDomains = [...new Set(fileResults.flatMap(item => item.serverDomains))];
const oldfakeipfilter = Array.isArray(yaml.dns["fake-ip-filter"]) ? yaml.dns["fake-ip-filter"] : [];
const newfakeipfilter = kzzDomains.map(domain => "+." + domain);

yaml.dns["fake-ip-filter"] = [
  ...new Set([
    ...newfakeipfilter,
    ...oldfakeipfilter
  ])
];

$.info(`[fake-ip-filter] 成功插入 ${newfakeipfilter.length} 个域名`);

// 5. 处理 proxy-server-nameserver-policy (严格区分文件，使用对应文件的 psnList，域名前面加 +.)
yaml.dns["proxy-server-nameserver-policy"] = yaml.dns["proxy-server-nameserver-policy"] || {};

for (const item of fileResults) {
  if (Array.isArray(item.psnList) && item.psnList.length > 0 && Array.isArray(item.serverDomains)) {
    for (const domain of item.serverDomains) {
      yaml.dns["proxy-server-nameserver-policy"][`+.${domain}`] = item.psnList;
    }
  }
}

// 6. 重新赋值 $content
$content = ProxyUtils.yaml.safeDump(yaml, {
  lineWidth: -1,
  forceQuotes: true
});

$.info("========== DNS脚本结束 ==========");
