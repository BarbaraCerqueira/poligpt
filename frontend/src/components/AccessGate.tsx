import React, { useState, useEffect, FormEvent, ReactNode } from 'react';
import poliLogo from '../assets/poligpt_logo.png';
import {
  ACCESS_DENIED_EVENT,
  captureAccessCodeFromUrl,
  getAccessCode,
  saveAccessCode,
  validateAccessCode,
} from '../services/api';

interface AccessGateProps {
  children: ReactNode;
}

// Restricts the chat to users with an access code while the prototype is not public
const AccessGate: React.FC<AccessGateProps> = ({ children }) => {
  const [hasAccess, setHasAccess] = useState(() => {
    captureAccessCodeFromUrl();
    return getAccessCode() !== null;
  });
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    const onAccessDenied = () => {
      setError('Seu código de acesso não é mais válido. Informe um novo código.');
      setHasAccess(false);
    };
    window.addEventListener(ACCESS_DENIED_EVENT, onAccessDenied);
    return () => window.removeEventListener(ACCESS_DENIED_EVENT, onAccessDenied);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedCode = code.trim();
    if (!trimmedCode || isChecking) return;

    setIsChecking(true);
    setError('');
    try {
      if (await validateAccessCode(trimmedCode)) {
        saveAccessCode(trimmedCode);
        setCode('');
        setHasAccess(true);
      } else {
        setError('Código de acesso inválido.');
      }
    } catch {
      setError('Não foi possível verificar o código. Tente novamente.');
    } finally {
      setIsChecking(false);
    }
  };

  if (hasAccess) return <>{children}</>;

  return (
    <div className="flex flex-col items-center justify-center h-full px-8 text-center">
      <img src={poliLogo} alt="PoliGPT" className="w-48 mb-8" />
      <h1 className="text-3xl font-bold text-gray-700 dark:text-gray-200/70 mb-3">
        Acesso restrito
      </h1>
      <p className="text-gray-600 dark:text-gray-400 max-w-md mb-8">
        O PoliGPT está em fase de testes. Para continuar, informe o código de acesso que você recebeu.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 w-full max-w-sm">
        <input
          type="password"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Código de acesso"
          autoComplete="off"
          autoFocus
          className="py-3 px-4 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
        />
        <button
          type="submit"
          disabled={!code.trim() || isChecking}
          className="py-3 rounded-2xl bg-blue-600 dark:bg-blue-500 text-white font-medium hover:bg-blue-700 dark:hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {isChecking ? 'Verificando...' : 'Entrar'}
        </button>
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </form>
    </div>
  );
};

export default AccessGate;
