---
title: "Incontro Febbraio 2014 - HHVM, Phalcon e Pthreads"
date: 2014-02-27 11:53:59 +0100
categories: ["sessioni"]
author: "Fabio Giannese"
original_url: "https://torino.grusp.org/incontro-febbraio-2014-hhvm-phalcon-e-pthread/"
redirect_from: ["/2014/02/incontro-febbraio-2014-hhvm-phalcon-e-pthread/"]
---

L'incontro di febbraio, più che un talk, è stata una sessione collaborativa su diversi argomenti, partendo da [HHVM](<http://www.hhvm.com/blog/> "HHVM").

Abbiamo installato su una macchina virtuale, creata con [Vagrant](<http://docs.vagrantup.com/v2/getting-started/index.html> "Vagrant"), una Debian Wheezy, seguendo poi le istruzioni del [Wiki su Github](<https://github.com/facebook/hhvm/wiki/Prebuilt-Packages-on-Debian-7>), con in parallelo la versione standard di PHP della distribuzione ("apt-get install php5"). Per velocizzare i tempi e non scriverci da zero il codice per fare benchmarking, abbiamo scaricato [uno script ](<http://www.php-benchmark-script.com>)che calcola i tempi di esecuzione di alcune funzionalità di base del linguaggio. Questi sono stati i risultati:  
[![Schermata 2014-02-27 alle 10.09.41](https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.09.41.png)](<https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.09.41.png>) [![Schermata 2014-02-27 alle 10.09.54](https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.09.54.png)](<https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.09.54.png>)  
HHVM compila il codice e lo [salva in un db SQLite](<http://www.sitepoint.com/hhvm-revisited/>), recuperandolo agli avvii successivi, ma dal test consecutivo fatto non sembra aver dato risultati migliori:  
[![Schermata 2014-02-27 alle 10.41.53](https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.41.53.png)](<https://torino.grusp.org/wp-content/uploads/2014/02/Schermata-2014-02-27-alle-10.41.53.png>)  
Inoltre, facendo girare un'applicazione esistente è emerso che non tutte le estensioni PHP [sono disponibili attualmente](<https://github.com/facebook/hhvm/wiki/Extensions>). Non abbiamo indagato ulteriormente (e ci riserviamo di farlo), ad una prima analisi perciò, ci è sembrato più performante e meno problematica una soluzione PHP + [OPCache](<http://it2.php.net/opcache>).

Parlando di [benchmark](<http://www.techempower.com/benchmarks/>) e codice precompilato, è naturalmente emerso [Phalcon](<http://phalconphp.com/en/>), un interessante framework [MVC ](<http://en.wikipedia.org/wiki/Model–view–controller>)scritto in C e compilato come estensione PHP. E' un esperimento degno di nota, ma tra gli svantaggi che può portare c'è la poca flessibilità delle API interne (se non si ha dimestichezza con C e moduli precopilati) e la diffusione del progetto ([Trends](<http://www.google.com/trends/explore#q=Phalcon%20PHP%2C%20Symfony2%2C%20Zend%20Framework>), [Github](<https://github.com/phalcon/cphalcon>), [Github Pulse](<https://github.com/phalcon/cphalcon/pulse>)).

E' stato poi il turno di [Pthreads](<http://it2.php.net/pthreads>) e processi multipli in background. La discussione è emersa dall'esigenza di utilizzare più risorse all'interno di un'esecuzione, in modo asincrono e perciò non bloccante. Questa [estensione Pecl](<http://pecl.php.net/package/pthreads>) ci è sembrata un'alternativa interessante alla gestione dei processi con l'utilizzo di [exec](<http://it2.php.net/function.exec>) o [shell_exec](<http://it2.php.net/shell_exec>) o [servizi più complessi](<https://github.com/videlalvaro/php-amqplib>).

Qualche spunto di riflessione anche sul [Garbage Collector](<http://www.php.net/manual/it/features.gc.php>) e problemi sulla [gestione della memoria](<https://bugs.php.net/bug.php?id=48781>) con le [Closure](<http://it1.php.net/Closure>) nelle prime versioni di PHP 5.3.
