import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./styles/foundation.css";
import "./styles/archive.css";
import "./styles/assistant.css";
import "./styles/vue.css";
import "./styles/observations.css";
import "./styles/forest.css";
import "./styles/cards.css";
import "./styles/taxonomy-scene.css";
import "./styles/journal-dialogs.css";
import "./styles/species-dossier.css";

createApp(App).use(router).mount("#app");
