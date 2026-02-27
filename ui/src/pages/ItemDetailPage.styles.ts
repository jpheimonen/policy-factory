/**
 * Styled components for the Item Detail page (placeholder).
 * Real content added in step 011.
 */
import styled from "styled-components";

export const PageWrapper = styled.div`
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  gap: ${({ theme }) => theme.spacing.md};
`;
