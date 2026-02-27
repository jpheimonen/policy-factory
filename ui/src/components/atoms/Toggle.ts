/**
 * Toggle atom.
 *
 * On/off switch component with animated transition.
 * Uses a hidden checkbox with a styled label for accessibility.
 */
import styled from "styled-components";

export type ToggleSize = "sm" | "md";

export interface ToggleProps {
  $size?: ToggleSize;
}

const sizes = {
  sm: { width: 32, height: 18, thumb: 14, offset: 2 },
  md: { width: 40, height: 22, thumb: 18, offset: 2 },
};

export const ToggleInput = styled.input<ToggleProps>`
  /* Hide native checkbox but keep it accessible */
  appearance: none;
  -webkit-appearance: none;
  position: relative;
  width: ${({ $size = "md" }) => sizes[$size].width}px;
  height: ${({ $size = "md" }) => sizes[$size].height}px;
  background: ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ $size = "md" }) => sizes[$size].height}px;
  cursor: pointer;
  transition:
    background ${({ theme }) => theme.transitions.fast};
  flex-shrink: 0;

  /* Thumb */
  &::after {
    content: "";
    position: absolute;
    top: ${({ $size = "md" }) => sizes[$size].offset}px;
    left: ${({ $size = "md" }) => sizes[$size].offset}px;
    width: ${({ $size = "md" }) => sizes[$size].thumb}px;
    height: ${({ $size = "md" }) => sizes[$size].thumb}px;
    background: ${({ theme }) => theme.colors.text.primary};
    border-radius: 50%;
    transition: transform ${({ theme }) => theme.transitions.fast};
  }

  /* Checked state */
  &:checked {
    background: ${({ theme }) => theme.colors.accent.blue};

    &::after {
      transform: translateX(${({ $size = "md" }) =>
        sizes[$size].width - sizes[$size].thumb - sizes[$size].offset * 2}px);
    }
  }

  /* Focus ring */
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.accent.blue};
    outline-offset: 2px;
  }

  /* Disabled state */
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

/**
 * Convenience wrapper: <Toggle /> renders a toggle switch.
 * Use ToggleInput directly if you need more control.
 */
export const Toggle = ToggleInput;
Toggle.defaultProps = { type: "checkbox" };
