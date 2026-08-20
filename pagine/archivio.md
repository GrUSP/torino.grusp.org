---
title: "Archivio"
permalink: /archivio/
---

Tutti gli articoli pubblicati dal PUG Torino, dal più recente.

{% assign posts_by_year = site.posts | group_by_exp: "post", "post.date | date: '%Y'" %}
{% for year in posts_by_year %}
## {{ year.name }}

<ul class="archive-list">
  {%- for post in year.items %}
  <li>
    <time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: '%d/%m' }}</time>
    <a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a>
  </li>
  {%- endfor %}
</ul>
{% else %}
Nessun articolo presente: esegui l'import dei contenuti WordPress.
{% endfor %}
