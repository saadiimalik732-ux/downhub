import { Container, getContainer } from "@cloudflare/containers";

export class DownHubContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "30m";
  enableInternet = true;
}

export default {
  async fetch(request, env) {
    return getContainer(
      env.DOWNHUB_CONTAINER,
      "downhub-main"
    ).fetch(request);
  },
};
