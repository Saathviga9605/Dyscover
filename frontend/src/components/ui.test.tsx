import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from './ui';

describe('design system', () => { it('renders a badge label', () => { render(<Badge>Research ready</Badge>); expect(screen.getByText('Research ready')).toBeTruthy(); }); });
