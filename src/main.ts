import { createApp } from "vue";

import MarshMethane from "./MarshMethane.vue";
import vuetify from "./plugins/vuetify.js";

import "@mdi/font/css/materialdesignicons.css";

// No WWT here any more: both globes live in iframes running earth-view.html,
// which is where the engine and its pinia store are installed. See
// vite.config.mts for why they cannot share this realm.
createApp(MarshMethane)
  .use(vuetify)
  .mount("#app-mount");
