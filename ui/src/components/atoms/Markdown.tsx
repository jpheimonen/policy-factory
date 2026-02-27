/**
 * Markdown rendering component.
 *
 * Renders a markdown string as styled, theme-aware HTML.
 * Supports standard markdown and GitHub-flavored markdown (GFM):
 * headings, paragraphs, bold, italic, links, lists, blockquotes,
 * inline code, code blocks, tables, task lists, and strikethrough.
 *
 * External links open in new tabs. Styling is consistent with
 * the design system via theme tokens.
 *
 * Follows the cc-runner Markdown.tsx pattern, simplified for
 * Policy Factory (no syntax highlighting or mermaid diagrams).
 */
import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import * as S from "./Markdown.styles.ts";

interface MarkdownProps {
  /** The markdown string to render */
  content: string;
}

/**
 * Determine if a URL points to an external site.
 */
function isExternalUrl(href: string | undefined): boolean {
  if (!href) return false;
  return href.startsWith("http://") || href.startsWith("https://");
}

/**
 * Renders markdown content as themed HTML with GFM support.
 * Memoized to avoid unnecessary re-renders on parent updates.
 */
export const Markdown = memo(function Markdown({ content }: MarkdownProps) {
  return (
    <S.Container>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Inline code
          code({ className, children, ...props }) {
            const isInline = !className;
            if (isInline) {
              return <S.InlineCode {...props}>{children}</S.InlineCode>;
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          // External links open in new tabs
          a({ href, children, ...props }) {
            const external = isExternalUrl(href);
            return (
              <a
                href={href}
                {...(external
                  ? { target: "_blank", rel: "noopener noreferrer" }
                  : {})}
                {...props}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </S.Container>
  );
});
