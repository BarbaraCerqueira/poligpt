import React, { useEffect, useRef } from 'react';
import ChatInput from '../components/ChatInput';
import ChatMessages from '../components/ChatMessages';
import SuggestionButtons from '../components/SuggestionButtons';
import Logo from '../components/Logo';
import { useChat } from '../hooks/useChat';

// Questions the assistant answers well (see the answer evaluation in evaluation/)
const suggestions = [
  'Como posso me inscrever em matérias?',
  'Qual é o procedimento para registrar um estágio?',
  'Quais são os requisitos para fazer intercâmbio pela Poli?',
];

const ChatPage: React.FC = () => {
  const { currentChat, currentChatId } = useChat();
  const messages = currentChat?.messages || [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  // The user is following the end of the conversation, unless they scrolled up to read
  const handleScroll = () => {
    const el = scrollRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  // A new message or another chat always goes to the end
  useEffect(() => {
    stickToBottom.current = true;
  }, [messages.length, currentChatId]);

  // Follows the answer as it is generated
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [currentChat?.messages]);

  return (
    <div className="grid grid-rows-[1fr_auto] h-full overflow-hidden">

      {/* Área de mensagens com a scrollbar propria */}
      <div ref={scrollRef} onScroll={handleScroll} className="overflow-y-auto scrollbar scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-700
        scrollbar-track-transparent hover:scrollbar-thumb-gray-400
        dark:hover:scrollbar-thumb-gray-600 scrollbar-thumb-rounded-full">
        <div className="flex flex-col min-h-full max-w-5xl mx-auto px-4 sm:px-8">
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center py-10">
              <Logo className="w-40 sm:w-48 mb-8" />
              <h1 className="text-3xl sm:text-4xl font-bold text-gray-700 dark:text-gray-200/70 mb-3">
                Como posso ajudar?
              </h1>
              <p className="text-gray-600 dark:text-gray-400 max-w-2xl">
                Sou o assistente virtual da Escola Politécnica da UFRJ. Respondo dúvidas acadêmicas
                e administrativas com base no site oficial da Poli, sempre indicando as fontes.
              </p>
              <div className="mt-8 w-full">
                <SuggestionButtons suggestions={suggestions} />
              </div>
            </div>
          ) : (
            <div className="pt-4 sm:pt-6 pb-8">
              <ChatMessages />
            </div>
          )}
        </div>
      </div>

      {/* Chat Input fixo na base da pagina*/}
      <div>
        <div className="max-w-5xl mx-auto mb-3 px-4 sm:px-14">
          <ChatInput />
          <p className="mt-2 text-center text-xs text-gray-500 dark:text-gray-400">
            O PoliGPT pode cometer erros. Confira as fontes indicadas nas respostas.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
