/**
 * 中国 30 城市经纬度坐标 + 图标
 * ================================
 * 与后端 city_metadata.py 完全对齐。
 * 用于 ECharts 地图 scatter 叠加层。
 */

export const CITY_METADATA = {
  北京: { lng: 116.40, lat: 39.90, icon: "🏯", province: "北京", region: "东部" },
  上海: { lng: 121.47, lat: 31.23, icon: "🗼", province: "上海", region: "东部" },
  广州: { lng: 113.26, lat: 23.13, icon: "🦐", province: "广东", region: "东部" },
  深圳: { lng: 114.07, lat: 22.62, icon: "💻", province: "广东", region: "东部" },
  杭州: { lng: 120.15, lat: 30.28, icon: "🪷", province: "浙江", region: "东部" },
  成都: { lng: 104.07, lat: 30.67, icon: "🐼", province: "四川", region: "西部" },
  武汉: { lng: 114.30, lat: 30.60, icon: "🍜", province: "湖北", region: "中部" },
  西安: { lng: 108.94, lat: 34.26, icon: "🏯", province: "陕西", region: "西部" },
  南京: { lng: 118.78, lat: 32.07, icon: "🏯", province: "江苏", region: "东部" },
  重庆: { lng: 106.55, lat: 29.57, icon: "🍲", province: "重庆", region: "西部" },
  昆明: { lng: 102.83, lat: 24.88, icon: "🌺", province: "云南", region: "西部" },
  贵阳: { lng: 106.71, lat: 26.65, icon: "🍶", province: "贵州", region: "西部" },
  南宁: { lng: 108.37, lat: 22.82, icon: "🍊", province: "广西", region: "西部" },
  海口: { lng: 110.20, lat: 20.02, icon: "🌴", province: "海南", region: "东部" },
  乌鲁木齐: { lng: 87.62, lat: 43.82, icon: "🍇", province: "新疆", region: "西部" },
  青岛: { lng: 120.38, lat: 36.07, icon: "🍺", province: "山东", region: "东部" },
  大连: { lng: 121.62, lat: 38.92, icon: "⚓", province: "辽宁", region: "东部" },
  厦门: { lng: 118.09, lat: 24.48, icon: "🏝️", province: "福建", region: "东部" },
  长沙: { lng: 112.97, lat: 28.23, icon: "🌶️", province: "湖南", region: "中部" },
  郑州: { lng: 113.62, lat: 34.75, icon: "🛕", province: "河南", region: "中部" },
  苏州: { lng: 120.58, lat: 31.30, icon: "🏯", province: "江苏", region: "东部" },
  天津: { lng: 117.20, lat: 39.13, icon: "🥟", province: "天津", region: "东部" },
  合肥: { lng: 117.23, lat: 31.82, icon: "🔬", province: "安徽", region: "中部" },
  福州: { lng: 119.30, lat: 26.08, icon: "🍵", province: "福建", region: "东部" },
  济南: { lng: 117.00, lat: 36.67, icon: "⛲", province: "山东", region: "东部" },
  沈阳: { lng: 123.43, lat: 41.80, icon: "🏮", province: "辽宁", region: "东部" },
  哈尔滨: { lng: 126.53, lat: 45.80, icon: "❄️", province: "黑龙江", region: "中部" },
  兰州: { lng: 103.83, lat: 36.07, icon: "🍜", province: "甘肃", region: "西部" },
  拉萨: { lng: 91.13, lat: 29.65, icon: "🏔️", province: "西藏", region: "西部" },
  呼和浩特: { lng: 111.75, lat: 40.84, icon: "🐑", province: "内蒙古", region: "西部" },
};

export const CITY_NAMES = Object.keys(CITY_METADATA);

export function getCityCoord(cityName) {
  const meta = CITY_METADATA[cityName];
  return meta ? [meta.lng, meta.lat] : null;
}

export function getCityIcon(cityName) {
  const meta = CITY_METADATA[cityName];
  return meta ? meta.icon : "📍";
}
