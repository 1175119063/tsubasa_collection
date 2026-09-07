import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./styles/foundation.css";
import "./styles/archive.css";
import "./styles/assistant.css";
import "./styles/vue.css";
import "./styles/observations.css";

createApp(App).use(router).mount("#app");
