import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { Marca } from "../components/brand/Marca"
import { EMAIL_SUPORTE, MAILTO_SUPORTE } from "../lib/contato"

// Política de Privacidade e Termos de Uso — exigidos pelo Google pra
// publicar o "Entrar com Google" (tela de consentimento pede os dois links)
// e necessários de qualquer forma pra um SaaS que guarda dados fiscais.
// Versão inicial, escrita em linguagem simples: deve ser revisada por um
// advogado antes de crescer a base de clientes (especialmente o
// controlador dos dados, que ainda não tem CNPJ próprio).

const ATUALIZADO_EM = "8 de outubro de 2026"

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{titulo}</h2>
      <div className="mt-2 space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{children}</div>
    </section>
  )
}

function Moldura({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas dark:bg-canvas-dark">
      <header className="border-b border-slate-200/70 dark:border-slate-800">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" aria-label="Agente Ana — início">
            <Marca />
          </Link>
          <Link to="/" className="text-sm text-slate-600 hover:text-accent-600 dark:text-slate-300">
            Voltar ao início
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{titulo}</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Última atualização: {ATUALIZADO_EM}</p>
        {children}
        <p className="mt-10 border-t border-slate-200 pt-6 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
          Dúvidas? Escreva pra{" "}
          <a href={MAILTO_SUPORTE} className="font-medium text-accent-600 hover:underline">
            {EMAIL_SUPORTE}
          </a>
          .
        </p>
      </main>
    </div>
  )
}

export function PrivacidadePage() {
  return (
    <Moldura titulo="Política de Privacidade">
      <p className="mt-6 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
        Esta política explica quais dados a Agente Ana (agenteana.com.br) coleta, por que coleta e como você controla
        esses dados, nos termos da Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018).
      </p>

      <Secao titulo="1. Dados que coletamos">
        <p>
          <b>Conta:</b> seu e-mail, o WhatsApp que você informa no cadastro (para a nossa equipe falar com você) e sua
          senha (guardada só em forma criptografada, que nem nós conseguimos ler). Se você
          entrar com o Google, recebemos do Google apenas seu nome, e-mail e um identificador da conta — nunca sua senha
          do Google nem acesso a Gmail, Drive ou outros serviços.
        </p>
        <p>
          <b>Dados da empresa emissora:</b> CNPJ, razão social, endereço, inscrição municipal, telefone, alíquota do
          Simples Nacional e o certificado digital A1 que você enviar, que fica guardado de forma criptografada.
        </p>
        <p>
          <b>Dados das notas:</b> fornecedores/tomadores que você cadastra (CNPJ, razão social, endereço, contatos),
          descrição dos serviços, valores, notas emitidas, recebimentos e despesas que você registrar.
        </p>
        <p>
          <b>Extratos bancários:</b> quando você envia um PDF de extrato, ele é lido só para sugerir quais pagamentos
          correspondem às suas notas. Guardamos apenas os recebimentos que você confirmar.
        </p>

        <p>
          <b>Uso do painel:</b> registramos quais telas você abre, quais ações faz (por exemplo, "gerou uma nota") e quando
          uma ação é recusada por erro — apenas o nome da tela ou da ação, a data e a conta, nunca o conteúdo das suas notas
          ou do seu financeiro. Serve para entendermos o que é usado e onde as pessoas encontram dificuldade. Esses registros
          são apagados depois de 180 dias.
        </p>
      </Secao>

      <Secao titulo="2. Para que usamos">
        <p>
          Para prestar o serviço que você contratou: montar, assinar e emitir suas notas fiscais de serviço, guardar o
          histórico, mostrar prazos e recebimentos, enviar mensagens e e-mails que você pedir, e manter sua conta segura.
          Também usamos seu e-mail para avisos da conta (confirmação de cadastro, cobrança, mudanças no serviço).
        </p>
        <p>Não vendemos seus dados e não usamos seus dados fiscais para publicidade.</p>
      </Secao>

      <Secao titulo="3. Com quem compartilhamos">
        <p>Somente com quem é necessário para o serviço funcionar:</p>
        <p>
          <b>Governo:</b> o Sistema Nacional da NFS-e (Receita Federal/prefeituras), que recebe as notas que você emite.
          <br />
          <b>Infraestrutura:</b> provedores de hospedagem e banco de dados, envio de e-mail e processamento de pagamentos,
          que tratam os dados apenas em nosso nome.
          <br />
          <b>Destinatários que você escolher:</b> quando você manda uma nota a um fornecedor por e-mail ou WhatsApp.
        </p>
        <p>
          <b>Sugestões de preenchimento:</b> o cadastro de empresas tomadoras (CNPJ, razão social e endereço, que são dados
          públicos) é compartilhado entre os usuários. Junto dele guardamos o código de serviço, o modelo de descrição e os
          prazos usados por último com cada tomador, que aparecem como sugestão para quem for faturar a mesma empresa — nunca
          valores, notas ou dados da sua conta.
        </p>
        <p>Também podemos compartilhar dados se uma lei ou ordem judicial exigir.</p>
      </Secao>

      <Secao titulo="4. Por quanto tempo guardamos">
        <p>
          Enquanto sua conta estiver ativa. Documentos fiscais podem precisar ser mantidos pelo prazo exigido pela
          legislação tributária. Se você encerrar a conta, apagamos ou anonimizamos o restante em até 90 dias.
        </p>
      </Secao>

      <Secao titulo="5. Segurança">
        <p>
          Cada conta só enxerga os próprios dados. Senhas e certificados ficam criptografados e toda a comunicação com o
          site usa conexão segura (HTTPS). Nenhum sistema é 100% invulnerável; se houver um incidente que afete seus
          dados, avisaremos você.
        </p>
      </Secao>

      <Secao titulo="6. Seus direitos">
        <p>
          Você pode pedir acesso, correção, portabilidade ou exclusão dos seus dados, e saber com quem eles foram
          compartilhados. É só escrever para {EMAIL_SUPORTE}.
        </p>
      </Secao>

      <Secao titulo="7. Cookies">
        <p>
          Usamos apenas um cookie essencial, que mantém você conectado ao sistema. Não usamos cookies de publicidade.
        </p>
      </Secao>

      <Secao titulo="8. Mudanças nesta política">
        <p>
          Se esta política mudar de forma relevante, avisaremos por e-mail ou dentro do sistema antes da mudança valer.
        </p>
      </Secao>
    </Moldura>
  )
}

export function TermosPage() {
  return (
    <Moldura titulo="Termos de Uso">
      <p className="mt-6 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
        Ao criar uma conta na Agente Ana (agenteana.com.br), você concorda com estes termos.
      </p>

      <Secao titulo="1. O serviço">
        <p>
          A Agente Ana é uma ferramenta online que ajuda a preparar, emitir e organizar notas fiscais de serviço
          eletrônicas (NFS-e) no padrão nacional, além de acompanhar prazos e recebimentos.
        </p>
      </Secao>

      <Secao titulo="2. Suas responsabilidades">
        <p>
          As informações fiscais das notas são de sua responsabilidade: dados dos tomadores, descrição e código do
          serviço, alíquota do Simples Nacional, valores e datas. A Agente Ana prepara a nota com o que você cadastrou,
          mas nenhuma nota é emitida sem a sua conferência e aprovação. Recomendamos confirmar as regras da sua
          atividade com o seu contador.
        </p>
        <p>
          Você é responsável por manter sua senha em sigilo e por usar um certificado digital válido, em nome da
          empresa que emite as notas.
        </p>
      </Secao>

      <Secao titulo="3. Teste grátis e pagamento">
        <p>
          Novas contas têm um período de teste gratuito. Depois dele, o uso continua mediante assinatura, cobrada de
          forma recorrente, sem fidelidade: você pode cancelar quando quiser, e o acesso segue até o fim do período já
          pago.
        </p>
      </Secao>

      <Secao titulo="4. Disponibilidade">
        <p>
          Trabalhamos para manter o serviço sempre no ar, mas ele depende também do Sistema Nacional da NFS-e e de
          outros serviços de terceiros, que podem ficar indisponíveis. Não garantimos funcionamento ininterrupto.
        </p>
      </Secao>

      <Secao titulo="5. Limitação de responsabilidade">
        <p>
          A Agente Ana não responde por multas, tributos ou prejuízos decorrentes de informações incorretas cadastradas
          pelo usuário, de indisponibilidade de sistemas do governo ou de uso em desacordo com estes termos. Em qualquer
          caso, nossa responsabilidade fica limitada ao valor pago por você nos últimos 12 meses.
        </p>
      </Secao>

      <Secao titulo="6. Uso proibido">
        <p>
          É proibido usar o serviço para emitir notas falsas ou em nome de terceiros sem autorização, tentar acessar
          dados de outras contas ou prejudicar o funcionamento do sistema. Contas nessas situações podem ser suspensas.
        </p>
      </Secao>

      <Secao titulo="7. Privacidade">
        <p>
          O tratamento dos seus dados segue a nossa{" "}
          <Link to="/privacidade" className="font-medium text-accent-600 hover:underline">
            Política de Privacidade
          </Link>
          .
        </p>
      </Secao>

      <Secao titulo="8. Mudanças e foro">
        <p>
          Podemos atualizar estes termos; mudanças relevantes serão avisadas com antecedência. Estes termos seguem as
          leis brasileiras.
        </p>
      </Secao>
    </Moldura>
  )
}
