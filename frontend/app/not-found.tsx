import Link from "next/link";

export default function NotFound() {
  return (
    <main className="not-found-page">
      <h1>페이지를 찾을 수 없어요</h1>
      <p>요청하신 화면이 없거나 이동되었어요.</p>
      <Link href="/">처음으로 돌아가기</Link>
    </main>
  );
}
