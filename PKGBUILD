pkgname=news
pkgver=1.0
pkgrel=1
pkgdesc="Terminal CS and AI related news reader with clickable links"
arch=('any')
url="https://github.com/geekyved/news-aur"
license=('MIT')
depends=('python')
source=('news.py')
sha256sums=('55c3b1b1cac7bdce9639b64fb28bfe832622c7aa8bd426031eea21493276a485')
    
package() {
    install -Dm755 "${srcdir}/news.py" "${pkgdir}/usr/bin/news"
}
