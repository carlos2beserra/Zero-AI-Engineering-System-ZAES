import { defineConfig, defineDocs } from "fumadocs-mdx/config";
import { remarkMermaid } from "./src/lib/remark-mermaid";

export const { docs, meta } = defineDocs({});

export default defineConfig({
  mdxOptions: {
    remarkPlugins: [remarkMermaid],
  },
});
