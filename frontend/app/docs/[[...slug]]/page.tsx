import { notFound } from "next/navigation";
import { DocsBody, DocsDescription, DocsPage, DocsTitle } from "fumadocs-ui/layouts/docs/page";
import mdxComponents from "fumadocs-ui/mdx";
import { docsSource } from "@/lib/docs-source";

type Props = { params: Promise<{ slug?: string[] }> };

export function generateStaticParams() {
  return docsSource.generateParams();
}

async function readPage({ params }: Props) {
  const { slug } = await params;
  return docsSource.getPage(slug) ?? notFound();
}

export async function generateMetadata(props: Props) {
  const { data, url } = await readPage(props);
  return { title: data.title + " | Docs", description: data.description, alternates: { canonical: url } };
}

export default async function Page(props: Props) {
  const { data } = await readPage(props);
  const Content = data.body;
  return (
    <DocsPage toc={data.toc}>
      <DocsTitle>{data.title}</DocsTitle>
      <DocsDescription>{data.description}</DocsDescription>
      <DocsBody><Content components={mdxComponents} /></DocsBody>
    </DocsPage>
  );
}
