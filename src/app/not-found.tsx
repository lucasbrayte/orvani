import Link from "next/link";

export default function NotFound() {
  return <div className="not-found"><span>404</span><h1>Não encontramos essa oferta.</h1><p>Ela pode ter sido removida, desativada ou o endereço pode estar incorreto.</p><Link className="button" href="/catalogo">Voltar ao catálogo</Link></div>;
}
