import { createApp, type Plugin } from "vue";

import { WWTComponent, wwtPinia } from "@wwtelescope/engine-pinia";

import MarshMethane from "./MarshMethane.vue";
import vuetify from "./plugins/vuetify.js";

import "@mdi/font/css/materialdesignicons.css";

createApp(MarshMethane, {
  wwtNamespace: "marsh-methane"
})
  .use(wwtPinia as unknown as Plugin<[]>)
  .use(vuetify)

  .component("WorldWideTelescope", WWTComponent)

  .mount("#app-mount");
