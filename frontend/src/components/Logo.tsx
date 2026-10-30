import React from 'react';
import logoLight from '../assets/poligpt_logo.png';
import logoDark from '../assets/poligpt_logo_dark.png';

interface LogoProps {
  className?: string;
}

// The dark theme uses a version with a thin white outline, since the navy "Poli" disappears on dark backgrounds
const Logo: React.FC<LogoProps> = ({ className = '' }) => (
  <>
    <img src={logoLight} alt="PoliGPT" className={`${className} dark:hidden`} />
    <img src={logoDark} alt="PoliGPT" className={`${className} hidden dark:block`} />
  </>
);

export default Logo;
