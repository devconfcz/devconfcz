(function ($) {
  $(document).ready(function(){

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
