# frozen_string_literal: true

# Apre in una scheda nuova i link ESTERNI del corpo degli articoli e delle
# pagine, aggiungendo target="_blank" e un rel sicuro.
#
# Perche' un plugin e non gli attributi inline di kramdown: i link da marcare
# sono decine, sparsi in 26 articoli importati da WordPress, e ce ne saranno
# altri. Si fa una volta sola in fase di build.
#
# Perche' funziona su GitHub Pages: il deploy non usa il builder classico di
# Pages ma `bundle exec jekyll build` su un runner (.github/workflows/jekyll.yml),
# quindi i plugin in _plugins/ vengono eseguiti, senza whitelist e senza gemme
# nuove.
#
# L'hook e' :post_convert e non :post_render. In :post_render l'output e' la
# pagina intera, layout compreso: header, nav, footer e paginazione finirebbero
# nella riscrittura. In :post_convert il Markdown e' gia' diventato HTML ma il
# layout non e' ancora stato applicato, quindi `doc.content` e' soltanto il
# corpo del documento (jekyll-4.4.1/lib/jekyll/renderer.rb, render_document).
#
# Interruttore in _config.yml:
#
#   external_links:
#     target_blank: true              # false per spegnere tutto
#     rel: "noopener noreferrer"      # rel da aggiungere ai link esterni
#
# Nota: gli excerpt non passano da qui (Jekyll::Excerpt#trigger_hooks e' un
# no-op), quindi le anteprime in home restano come sono.
module PugTorino
  module ExternalLinks
    DEFAULT_REL = "noopener noreferrer"

    # Tag <a> di apertura, con i suoi attributi grezzi.
    ANCHOR_TAG = %r{<a\b([^>]*)>}i
    # href tra virgolette doppie, singole o senza virgolette.
    HREF_ATTR  = %r{\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))}i
    TARGET_ATTR = %r{\btarget\s*=}i
    REL_ATTR   = %r{\brel\s*=\s*(?:"([^"]*)"|'([^']*)')}i

    # Schemi che non aprono una pagina web: non vanno mai marcati.
    NON_WEB_SCHEME = %r{\A(?:mailto|tel|sms|javascript|data|ftp|file):}i

    class << self
      # true se l'interruttore in _config.yml e' acceso (default: acceso).
      def enabled?(site)
        config(site).fetch("target_blank", true)
      end

      def rel_for(site)
        rel = config(site)["rel"]
        rel.nil? || rel.to_s.strip.empty? ? DEFAULT_REL : rel.to_s.strip
      end

      def config(site)
        conf = site.config["external_links"]
        conf.is_a?(Hash) ? conf : {}
      end

      # Host che vanno considerati interni: quello di `url` in _config.yml,
      # quello del file CNAME e le rispettive varianti con www.
      # Gli articoli importati da WordPress sono pieni di link assoluti a
      # torino.grusp.org, che sono link interni travestiti.
      def internal_hosts(site)
        @internal_hosts ||= {}
        @internal_hosts[site.object_id] ||= begin
          hosts = [host_of(site.config["url"].to_s)]
          cname = File.join(site.source, "CNAME")
          hosts << File.read(cname).strip if File.file?(cname)
          hosts = hosts.compact.map { |h| h.to_s.downcase }.reject(&:empty?)
          hosts.flat_map { |h| [h, h.sub(%r{\Awww\.}, ""), "www.#{h.sub(%r{\Awww\.}, "")}"] }.uniq
        end
      end

      # Host di una URL assoluta o protocol-relative; nil se e' relativa.
      def host_of(url)
        if url.start_with?("//")
          url[2..].to_s.split(%r{[/?#]}, 2).first
        elsif (match = %r{\Ahttps?://([^/?#]+)}i.match(url))
          match[1]
        end
      end

      # Un link e' esterno solo se punta a un host diverso dal nostro.
      # Restano fuori: relativi, /assoluti-di-percorso, #ancore, ?query,
      # mailto:, tel:, javascript: e compagnia.
      def external?(href, hosts)
        url = href.to_s.strip
        return false if url.empty?
        return false if url.start_with?("#", "?", ".")
        return false if NON_WEB_SCHEME.match?(url)

        host = host_of(url)
        return false if host.nil? # relativa o assoluta di percorso (/...)

        !hosts.include?(host.downcase.sub(%r{\A.*@}, ""))
      end

      # Riscrive i soli tag <a> di apertura che puntano fuori dal sito.
      def rewrite(content, hosts, rel)
        content.gsub(ANCHOR_TAG) do |tag|
          attrs = Regexp.last_match(1).to_s
          href_match = HREF_ATTR.match(attrs)
          next tag if href_match.nil?

          href = href_match[1] || href_match[2] || href_match[3]
          next tag unless external?(href, hosts)
          # Un target scritto a mano nell'articolo ha la precedenza.
          next tag if TARGET_ATTR.match?(attrs)

          "<a #{merge_rel(attrs, rel).strip} target=\"_blank\">"
        end
      end

      # Aggiunge i token di rel mancanti senza sovrascrivere quelli gia' presenti.
      def merge_rel(attrs, rel)
        tokens = rel.split(%r{\s+})
        existing = REL_ATTR.match(attrs)
        return "#{attrs} rel=\"#{rel}\"" if existing.nil?

        current = (existing[1] || existing[2]).to_s.split(%r{\s+}).reject(&:empty?)
        merged = (current + tokens).uniq
        attrs.sub(REL_ATTR, "rel=\"#{merged.join(" ")}\"")
      end

      def process(doc)
        site = doc.site
        return unless enabled?(site)
        return unless doc.output_ext == ".html"

        doc.content = rewrite(doc.content.to_s, internal_hosts(site), rel_for(site))
      end
    end
  end
end

# :documents copre tutte le collezioni, quindi anche i post: registrarsi anche
# su :posts farebbe scattare l'hook due volte sullo stesso documento.
Jekyll::Hooks.register :documents, :post_convert do |doc|
  PugTorino::ExternalLinks.process(doc)
end

# Le pagine statiche (chi siamo, contatti, archivio) seguono la stessa regola.
Jekyll::Hooks.register :pages, :post_convert do |page|
  PugTorino::ExternalLinks.process(page)
end
