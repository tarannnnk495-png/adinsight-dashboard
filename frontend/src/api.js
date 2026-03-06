import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

export const api = {
  getCompetitors: async () => {
    const response = await API.get("/competitors");
    return response.data;
  },
  getSyncStatus: async () => {
    const response = await API.get("/sync/status");
    return response.data;
  },
  triggerSync: async (maxAdsPerBrand = 20) => {
    const response = await API.post("/sync/now", {
      max_ads_per_brand: maxAdsPerBrand,
    });
    return response.data;
  },
  getDashboardAnalytics: async (recencyDays = 90) => {
    const response = await API.get("/analytics/dashboard", {
      params: { recency_days: recencyDays },
    });
    return response.data;
  },
  getAds: async (params) => {
    const response = await API.get("/ads", { params });
    return response.data;
  },
  generateInsights: async (recencyDays = 90) => {
    const response = await API.post("/insights/generate", {
      recency_days: recencyDays,
    });
    return response.data;
  },
  getLatestInsights: async () => {
    const response = await API.get("/insights/latest");
    return response.data;
  },
};
