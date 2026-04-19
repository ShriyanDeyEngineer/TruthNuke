/**
 * Example test to verify Jest and React Testing Library are configured correctly.
 * 
 * This file can be removed once actual tests are implemented.
 */

import { render, screen } from '@testing-library/react';

describe('Testing Infrastructure', () => {
  it('should pass a simple test', () => {
    expect(true).toBe(true);
  });

  it('should have jest-dom matchers available', () => {
    const div = document.createElement('div');
    div.textContent = 'Hello, TruthNuke!';
    document.body.appendChild(div);
    
    expect(div).toBeInTheDocument();
    expect(div).toHaveTextContent('Hello, TruthNuke!');
    
    document.body.removeChild(div);
  });

  it('should render a simple React component', () => {
    const TestComponent = () => <div data-testid="test">Test Content</div>;
    
    render(<TestComponent />);
    
    expect(screen.getByTestId('test')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});
