import { visit } from "unist-util-visit";
import type { Root, Code } from "mdast";
import type { MdxJsxFlowElement } from "mdast-util-mdx-jsx";

/**
 * Remark plugin that converts ```mermaid code blocks into <Mermaid chart="..." />
 * JSX elements so the Mermaid React component renders them visually.
 */
export function remarkMermaid() {
  return function transformer(tree: Root) {
    visit(tree, "code", (node: Code, index, parent) => {
      if (node.lang !== "mermaid" || !parent || index == null) return;

      const jsxNode: MdxJsxFlowElement = {
        type: "mdxJsxFlowElement",
        name: "Mermaid",
        attributes: [
          {
            type: "mdxJsxAttribute",
            name: "chart",
            value: node.value,
          },
        ],
        children: [],
      };

      parent.children.splice(index, 1, jsxNode as never);
    });
  };
}
