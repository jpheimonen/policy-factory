/**
 * TypeScript module augmentation for styled-components.
 *
 * Extends DefaultTheme with our Theme type so that all
 * theme property accesses in styled components are type-checked
 * at compile time.
 */
import "styled-components";
import type { Theme } from "./theme.ts";

declare module "styled-components" {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefaultTheme extends Theme {}
}
