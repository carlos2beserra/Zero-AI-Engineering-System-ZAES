import { source } from "@/lib/source";
import { createFromSource } from "fumadocs-core/search/server";

// Static HTML export (`output: "export"`): emit the search index as a static
// JSON file at build time. The client downloads it and runs Orama in-browser.
export const revalidate = false;

export const { staticGET: GET } = createFromSource(source);
