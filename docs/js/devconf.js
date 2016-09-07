(function ($) {
  $(document).ready(function(){

  // FIXME: if page is refreshed while lower at the bottom of the page the navbar does appear...
  // eg, load page, scroll down (navbar appears), CTRL-R... navbar remains hidden even though
  // we are far down the page
  // hide .navbar first
  $(".navbar").hide();

  // fade in .navbar
  $(function () {
    $(window).scroll(function () {
      // set distance user needs to scroll before we fadeIn navbar
      // FIXME: Make this START at the ABOUT page
      logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top
      if ($(this).scrollTop() > logo_pos) {
        $('.navbar').fadeIn();
      } else {
        $('.navbar').fadeOut();
      }
    });


  });

});
  }(jQuery));
